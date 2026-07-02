"""Regime Classification Strategy using ML models.

This strategy classifies market regimes (trending, mean-reverting, etc.)
and can be used to select appropriate trading strategies for each regime.

IMPLEMENTATION GUIDANCE:
========================

1. REGIME DEFINITIONS
   - What regimes matter for your trading?

   Option A: Volatility-based
     * Low volatility (calm, good for trend following)
     * High volatility (choppy, good for mean reversion)
     * Can use VIX or realized volatility

   Option B: Trend vs Mean-Reversion
     * Trending regime (use momentum strategies)
     * Mean-reverting regime (use mean reversion strategies)
     * Identified by autocorrelation or Hurst exponent

   Option C: Regime-based on market structure
     * Bull market (rising trend, lower vol)
     * Bear market (falling trend, higher vol)
     * Consolidation (low trend, moderate vol)
     * Shock (extreme moves, very high vol)

   Option D: ML-discovered regimes
     * Let model find optimal regimes via clustering
     * Regime may not have intuitive names

2. REGIME IDENTIFICATION FEATURES
   - Trend indicators:
     * ADX (trend strength)
     * Moving average slope
     * Hurst exponent (trending vs mean-reverting)

   - Volatility measures:
     * Rolling std (20d, 60d)
     * ATR (Average True Range)
     * Volatility of volatility

   - Mean reversion indicators:
     * Autocorrelation of returns
     * Distance from moving averages
     * Z-score levels

   - Market internals (if available):
     * Advance/decline ratio
     * Put/call ratio
     * VIX level

   - Cross-asset:
     * Correlation between assets
     * Equity-bond correlation
     * Risk-on/risk-off sentiment indicators

3. MODEL APPROACHES

   Option A: Supervised Classification
     * Label historical periods by regime
     * Train classifier on features
     * Use for real-time regime prediction
     * Requires labeled historical data

   Option B: Unsupervised Clustering (Recommended for discovery)
     * K-Means or Mixture Models on feature space
     * Model discovers natural market groupings
     * Interpret clusters after training
     * Doesn't require pre-labeled data

   Option C: Hidden Markov Model (HMM)
     * Models regime transitions as Markov chain
     * Captures regime persistence (regime not random)
     * Good for probability of regime change

   Option D: Gaussian Mixture Model (GMM)
     * Similar to HMM but simpler
     * Works well for multi-regime scenarios
     * Provides probability of each regime

4. TRAINING METHODOLOGY
   - For supervised classification:
     * Define clear regime labels on historical data
     * Use stratified k-fold CV (ensure all regimes represented)
     * Score: F1 (imbalanced regimes), accuracy if balanced

   - For unsupervised clustering:
     * Normalize features (K-Means sensitive to scale)
     * Use elbow method or silhouette score for K selection
     * Validate regimes are economically meaningful

   - Handle regime persistence:
     * Markets stay in regimes for multiple periods
     * Use expanding window rather than point forecasts
     * Consider trend in regime transitions

5. STRATEGY INTEGRATION
   - Use regime to select strategies:
     * Regime A → Use strategy A
     * Regime B → Use strategy B
     * Can use RegimeSwitching base class

   - Use regime to adjust risk:
     * Increase position size in favorable regimes
     * Decrease when regime is unfavorable
     * More conservative in uncertain regimes

   - Use regime for entrytiming:
     * Only enter new longs in uptrends
     * Only enter new shorts in downtrends
     * Avoid counter-trend trades

   - Monitor regime transitions:
     * Regime changes may require rehedging
     * Transition periods are high risk
     * Track regime confidence/probability

6. VALIDATION & MONITORING
   - Backtesting:
     * Are identified regimes economically meaningful?
     * Do strategies tailored to regimes outperform?
     * What's accuracy of regime predictions?

   - Live monitoring:
     * Track actual regime vs predicted regime
     * Monitor prediction confidence
     * Retrain if regime definitions shift

   - Avoid overfitting:
     * Don't create too many regimes (overfitting)
     * Ensure regimes are stable over time
     * Use minimum 2-3 regimes, max 4-5 practical

NEXT STEPS:
===========
1. Choose regime definition (volatility, trend, or discover)
2. Define features for regime classification
3. Collect historical data and label periods
4. Train classification or clustering model
5. Integrate with strategy selection logic
6. Validate regime predictions on hold-out data
"""

import pandas as pd
import numpy as np
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from ..base_strategy import Strategy
from ...core_logic.events.base_event import Event

# ─────────────────────────────────────────────
# Load and align VIX data
# ─────────────────────────────────────────────

def load_vix(path: str) -> pd.Series:
    """Load VIX CSV from yfinance format and return a Close price Series."""
    vix = pd.read_csv(path, index_col=0, parse_dates=True)
    col = 'Close' if 'Close' in vix.columns else vix.columns[0]
    return vix[col].rename('VIX')


# ─────────────────────────────────────────────
# Feature engineer: what characterises a regime?
# ─────────────────────────────────────────────

REGIME_FEATURE_COLS = [
    'vol_20d',        # realized volatility
    'vol_60d',        # longer-term vol
    'ret_20d',        # medium-term trend direction
    'vix_level',      # implied vol / fear gauge
    'vix_change',     # is fear rising or falling?
    'dist_from_ma50', # how extended is price?
    'autocorr_5d',    # trending vs mean-reverting character
]

def build_regime_features(data: pd.DataFrame, vix: pd.Series) -> pd.DataFrame:
    """
    Engineer regime classification features from OHLCV + VIX.
    All features use only past data — no lookahead.
    """
    df = data.copy()

    # Align VIX to the same index (forward-fill any missing VIX dates)
    df['VIX'] = vix.reindex(df.index).ffill()

    # Realized volatility at two horizons
    ret = df['Close'].pct_change()
    df['vol_20d'] = ret.rolling(20).std() * np.sqrt(252)   # annualized
    df['vol_60d'] = ret.rolling(60).std() * np.sqrt(252)

    # Medium-term trend
    df['ret_20d'] = df['Close'].pct_change(20)

    # VIX features
    df['vix_level']  = df['VIX']
    df['vix_change'] = df['VIX'].pct_change(5)             # 5-day change in VIX

    # Distance from 50-day MA (mean reversion signal)
    df['ma50']        = df['Close'].rolling(50).mean()
    df['dist_from_ma50'] = (df['Close'] - df['ma50']) / df['ma50']

    # Return autocorrelation: positive = trending, negative = mean-reverting
    df['autocorr_5d'] = ret.rolling(20).apply(
        lambda x: x.autocorr(lag=5) if len(x) >= 6 else np.nan,
        raw=False,
    )

    df.dropna(inplace=True)
    return df

REGIME_NAMES = {
    0: 'bull',
    1: 'consolidation',
    2: 'bear',
}

def train_gmm(features_df: pd.DataFrame, n_regimes: int = 3) -> Pipeline:
    """
    Fit a Gaussian Mixture Model on regime features.

    The pipeline standardizes features first (GMM is sensitive to scale),
    then fits the GMM. Returns the fitted sklearn Pipeline.

    After fitting, call interpret_regimes() to figure out which
    cluster index maps to bull / bear / etc.
    """
    X = features_df[REGIME_FEATURE_COLS].values

    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('gmm', GaussianMixture(
            n_components=n_regimes,
            covariance_type='full',
            n_init=10,           # run 10 random inits, keep best
            random_state=42,
            max_iter=200,
        )),
    ])
    pipeline.fit(X)

    bic = pipeline.named_steps['gmm'].bic(
        pipeline.named_steps['scaler'].transform(X)
    )
    print(f"GMM fitted with {n_regimes} regimes. BIC = {bic:.1f}")
    print("(Lower BIC = better. Try n_regimes=2,3,4 and pick the elbow.)")
    return pipeline


def interpret_regimes(pipeline: Pipeline, features_df: pd.DataFrame):
    """
    Print cluster means so you can assign intuitive names to each regime index.
    Call this after train_gmm() to decide what 0/1/2 actually means.

    Example output:
        Regime 0: vol_20d=0.12, ret_20d=-0.05, vix_level=28.1 → likely 'bear'
        Regime 1: vol_20d=0.08, ret_20d=+0.03, vix_level=14.2 → likely 'bull'
        Regime 2: vol_20d=0.10, ret_20d=+0.00, vix_level=18.5 → likely 'consolidation'
    """
    scaler = pipeline.named_steps['scaler']
    gmm    = pipeline.named_steps['gmm']
    means  = scaler.inverse_transform(gmm.means_)   # back to original scale

    print("\n=== Regime cluster means (raw feature scale) ===")
    for i, mean in enumerate(means):
        vals = dict(zip(REGIME_FEATURE_COLS, mean))
        desc = "  ".join(f"{k}={v:+.3f}" for k, v in vals.items())
        print(f"  Regime {i}: {desc}")
    print("\nUpdate REGIME_NAMES dict based on the above.")


class RegimeClassification(Strategy):
    """ML-based regime classification strategy template.
    """
    CONFIDENCE_THRESHOLD = 0.60   # only act if dominant regime prob > 60%

    def __init__(self, data, vix_path: str, regime_model=None, n_regimes: int = 3):
        super().__init__(data)

        vix = load_vix(vix_path)
        self.features_df = build_regime_features(data, vix)

        if regime_model is None:
            print("No regime model provided — training GMM...")
            self.regime_model = train_gmm(self.features_df, n_regimes=n_regimes)
            interpret_regimes(self.regime_model, self.features_df)
        else:
            self.regime_model = regime_model

        # Pre-compute regime probabilities for every historical bar
        X = self.features_df[REGIME_FEATURE_COLS].values
        self._proba_df = pd.DataFrame(
            self.regime_model.predict_proba(X),
            index=self.features_df.index,
            columns=[REGIME_NAMES.get(i, f'regime_{i}') for i in range(n_regimes)],
        )

        self.current_regime = None
        self.regime_probabilities = None

    def compute_factors(self, asset, data):
        """Features are pre-computed in self.features_df at init."""
        pass

    def on_event(self, event: Event):
        t = event.timestamp

        if t not in self._proba_df.index:
            return 0

        proba = self._proba_df.loc[t]             # Series: {'bull': 0.72, ...}
        dominant_regime = proba.idxmax()           # e.g. 'bull'
        confidence      = proba.max()

        # Store for external access (e.g. by a meta-strategy)
        self.current_regime       = dominant_regime
        self.regime_probabilities = proba.to_dict()

        if confidence < self.CONFIDENCE_THRESHOLD:
            return 0   # uncertain — sit out

        # Simple directional mapping
        if dominant_regime == 'bull':
            return 1
        elif dominant_regime == 'bear':
            return -1
        else:
            return 0   # consolidation → flat

    def get_regime(self) -> str | None:
        """Return current regime label. Use this in a meta-strategy."""
        return self.current_regime

    def get_regime_probabilities(self) -> dict | None:
        """Return full probability distribution over regimes."""
        return self.regime_probabilities

    def get_regime_history(self) -> pd.DataFrame:
        """Return full probability time series — useful for plotting."""
        return self._proba_df
