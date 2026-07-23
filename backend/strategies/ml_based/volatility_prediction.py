"""Volatility Prediction Strategy using ML models.

This strategy predicts future volatility and adjusts position sizes or
trading intensity based on predicted volatility levels.

IMPLEMENTATION GUIDANCE:
========================

1. VOLATILITY PREDICTION TARGET
   - What to predict:
     * Realized volatility (next N days actual std of returns)
     * VIX-implied volatility if available
     * Volatility regime (low/medium/high)

   - Prediction horizon:
     * Short-term (1-5 days) for position sizing
     * Medium-term (1-4 weeks) for regime switching

2. VOLATILITY FEATURES
   - Historical volatility measures:
     * Rolling standard deviation (20d, 60d, etc.)
     * Historical returns autocorrelation
     * GARCH parameters (mean reversion of volatility)

   - Volume-based:
     * Volume levels relative to average
     * Volume spikes preceding volatility
     * Volume momentum

   - Microstructure:
     * Bid-ask spreads (if available)
     * Order book depth changes
     * Percentage of large trades

   - Cross-asset:
     * Correlation changes
     * VIX level (if trading equities)
     * Credit spreads (if available)

3. MODEL SELECTION
   - Regression models for volatility forecasts:
     * Linear regression (simple baseline)
     * Ridge/Lasso (prevents overfitting)
     * Gradient boosting (captures non-linearities)
     * GARCH/EGARCH (time-series specific)

   - Classification for volatility regimes:
     * Random Forest / Gradient Boosting
     * Define regimes: Low (<1%), Medium (1-2%), High (>2%)

4. TRAINING CONSIDERATIONS
   - Volatility forecasting challenges:
     * Volatility clustering: high volatility predicts future high volatility
     * But mean reversion: extreme volatility reverts back
     * Model GARCH-like dynamics

   - Data preprocessing:
     * Standardize/normalize volatility measures
     * Handle period effects (market close/open gaps)
     * Account for calendar effects (Friday, month-end, earnings)

5. USING VOLATILITY PREDICTIONS
   - Position sizing:
     * Reduce size when expecting high volatility
     * Increase size when expecting calm periods
     * Scale target volatility by predicted volatility

   - Strategy selection:
     * Use mean reversion in high-volatility regimes
     * Use momentum in low-volatility regimes
     * Can integrate with RegimeSwitching strategy

   - Stop loss adjustment:
     * Looser stops in high-volatility periods
     * Tighter stops in low-volatility periods

   - Trading decisions:
     * Skip trades when predicted volatility is extreme
     * Focus on high-probability setups in calm periods

6. VALIDATION
   - Backtesting:
     * Did predicted volatility match realized?
     * Did strategies using predictions outperform?
     * Check prediction accuracy metrics (MAE, RMSE, % correct direction)

   - Walk-forward:
     * Retrain monthly to capture changing volatility regimes
     * Monitor model degradation over time

NEXT STEPS:
===========
1. Collect historical volatility data
2. Engineer volatility features
3. Define volatility targets/regimes
4. Train regression or classification model
5. Integrate predictions into other strategies via position sizing
"""

import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error
from ..base_strategy import Strategy
from ...core_logic.events.base_event import Event


# ─────────────────────────────────────────────
# Load VIX (reuse same helper as regime strategy)
# ─────────────────────────────────────────────

def load_vix(path: str) -> pd.Series:
    vix = pd.read_csv(path, index_col=0, parse_dates=True)
    col = 'Close' if 'Close' in vix.columns else vix.columns[0]
    return vix[col].rename('VIX')


# ─────────────────────────────────────────────
# Feature engineering
# ─────────────────────────────────────────────

VOL_FEATURE_COLS = [
    'vol_5d', 'vol_10d', 'vol_20d', 'vol_60d',  # volatility at multiple horizons
    'vol_of_vol',                                  # vol is itself volatile
    'vol_ratio',                                   # short vs long vol (regime indicator)
    'volume_spike',                                # unusual volume often precedes vol
    'volume_trend',
    'ret_autocorr',                                # trending vs mean-reverting
    'vix_level',                                   # implied vol (fear gauge)
    'vix_change_5d',
    'day_of_week',                                 # calendar effects (Friday vol premium)
    'month',                                       # seasonal patterns
]


def build_vol_features(data: pd.DataFrame, vix: pd.Series | None = None) -> pd.DataFrame:
    """
    Engineer volatility prediction features from OHLCV (+ optional VIX).
    Target: realized vol over the *next* 5 trading days (annualized).
    All features use only past data — no lookahead.
    """
    df = data.copy()
    ret = df['Close'].pct_change()

    # ── Volatility at multiple horizons (annualized) ──
    df['vol_5d']  = ret.rolling(5).std()  * np.sqrt(252)
    df['vol_10d'] = ret.rolling(10).std() * np.sqrt(252)
    df['vol_20d'] = ret.rolling(20).std() * np.sqrt(252)
    df['vol_60d'] = ret.rolling(60).std() * np.sqrt(252)

    # ── Volatility of volatility (meta-feature: is vol itself changing?) ──
    df['vol_of_vol'] = df['vol_20d'].rolling(20).std()

    # ── Short/long vol ratio (>1 = vol picking up, <1 = calming) ──
    df['vol_ratio'] = df['vol_5d'] / df['vol_60d'].replace(0, np.nan)

    # ── Volume features ──
    vol_ma = df['Volume'].rolling(20).mean()
    df['volume_spike'] = df['Volume'] / vol_ma.replace(0, np.nan)   # >1 = spike
    df['volume_trend'] = vol_ma.pct_change(5)

    # ── Return autocorrelation (positive = trending, negative = reverting) ──
    df['ret_autocorr'] = ret.rolling(20).apply(
        lambda x: x.autocorr(lag=1) if len(x) >= 2 else np.nan,
        raw=False,
    )

    # ── VIX features (if available) ──
    if vix is not None:
        df['vix_level']    = vix.reindex(df.index).ffill()
        df['vix_change_5d'] = df['vix_level'].pct_change(5)
    else:
        df['vix_level']    = 0.0
        df['vix_change_5d'] = 0.0

    # ── Calendar effects ──
    df['day_of_week'] = df.index.dayofweek   # 0=Mon … 4=Fri
    df['month']       = df.index.month

    # ── Target: realized vol over NEXT 5 days (only used in training) ──
    # shift(-5) = look 5 rows into the future — training-time only, not inference
    df['target_vol'] = ret.shift(-1).rolling(5).std().shift(-4) * np.sqrt(252)

    df.dropna(inplace=True)
    return df


# ─────────────────────────────────────────────
# Train LightGBM regressor
# ─────────────────────────────────────────────

def train_vol_model(features_df: pd.DataFrame) -> lgb.LGBMRegressor:
    """
    Train a LightGBM regressor to predict next-5d realized volatility.
    Uses time-ordered split — never random.
    """
    # Drop the last 5 rows — they have no valid target (future not yet realized)
    df = features_df.iloc[:-5]

    X = df[VOL_FEATURE_COLS]
    y = df['target_vol']

    # Time-ordered split
    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    model = lgb.LGBMRegressor(
        n_estimators=300,
        learning_rate=0.03,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_samples=20,   # prevents overfitting on small vol clusters
        random_state=42,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )

    preds = model.predict(X_test)
    mae   = mean_absolute_error(y_test, preds)
    corr  = np.corrcoef(y_test, preds)[0, 1]
    print(f"Vol model — MAE: {mae:.4f}  |  Rank corr: {corr:.3f}")
    print("(MAE in annualized vol units; corr > 0.5 is a reasonable target)")

    # Print feature importances so you can prune unhelpful features
    imp = pd.Series(model.feature_importances_, index=VOL_FEATURE_COLS)
    print("\nTop features:\n", imp.sort_values(ascending=False).head(8).to_string())

    return model


class VolatilityPrediction(Strategy):
    """
    Predicts next-5d realized volatility and exposes it for position sizing.

    This strategy rarely generates +1/-1 signals on its own.
    Its main output is get_position_scale(), which other strategies
    can call to shrink or grow their positions based on predicted vol.

    Typical integration:
        vol_strategy  = VolatilityPrediction(data, vix_path=VIX_PATH)
        dir_strategy  = DirectionalPrediction(data)

        raw_signal    = dir_strategy.on_event(event)
        scale         = vol_strategy.get_position_scale(target_vol=0.10)
        final_signal  = raw_signal * scale       # e.g. 1 * 0.5 = half position
    """

    TARGET_VOL = 0.10          # 10% annualized — adjust to your risk appetite
    MAX_SCALE  = 2.0           # never lever up more than 2x
    MIN_SCALE  = 0.1           # never go below 10% of normal size

    def __init__(self, data, vix_path: str | None = None, vol_model=None):
        super().__init__(data)

        vix = load_vix(vix_path) if vix_path else None
        self.features_df = build_vol_features(data, vix)

        if vol_model is None:
            print("No vol model provided — training LightGBM regressor...")
            self.vol_model = train_vol_model(self.features_df)
        else:
            self.vol_model = vol_model

        # Pre-compute predictions for every bar
        X = self.features_df[VOL_FEATURE_COLS]
        self._pred_series = pd.Series(
            self.vol_model.predict(X),
            index=self.features_df.index,
            name='predicted_vol',
        )

        self.predicted_vol: float | None = None

    def compute_factors(self, asset, data):
        """Features pre-computed at init."""
        pass

    def on_event(self, event: Event, positions=None) -> int:
        t = event.timestamp

        if t not in self._pred_series.index:
            return 0

        self.predicted_vol = float(self._pred_series.loc[t])

        # Volatility prediction alone doesn't tell you direction.
        # Return 0 here; use get_position_scale() from another strategy.
        return 0

    # ── Public interface for other strategies ──────────────────────────

    def get_position_scale(self, target_vol: float | None = None) -> float:
        """
        Return a position size multiplier based on predicted volatility.

        Formula: scale = target_vol / predicted_vol
        - predicted_vol high → scale < 1 (smaller position)
        - predicted_vol low  → scale > 1 (larger position, up to MAX_SCALE)

        Args:
            target_vol: desired annualized portfolio volatility (default TARGET_VOL)

        Returns:
            float in [MIN_SCALE, MAX_SCALE]
        """
        if self.predicted_vol is None or self.predicted_vol <= 0:
            return 1.0

        tv    = target_vol or self.TARGET_VOL
        scale = tv / self.predicted_vol
        return float(np.clip(scale, self.MIN_SCALE, self.MAX_SCALE))

    def get_predicted_vol(self) -> float | None:
        """Return raw predicted annualized volatility for the current bar."""
        return self.predicted_vol

    def get_vol_regime(self) -> str:
        """
        Classify predicted vol into a human-readable regime.
        Thresholds are annualized; tune these to your asset class.
        """
        if self.predicted_vol is None:
            return 'unknown'
        if self.predicted_vol < 0.10:
            return 'low'
        elif self.predicted_vol < 0.20:
            return 'medium'
        else:
            return 'high'

    def get_vol_history(self) -> pd.Series:
        """Return full predicted vol time series — useful for plotting."""
        return self._pred_series