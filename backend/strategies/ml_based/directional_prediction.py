"""Direction Prediction Strategy using ML models.

This strategy uses a trained machine learning classifier to predict
whether the price will go up or down, then trades based on predictions.

IMPLEMENTATION GUIDANCE:
========================

1. FEATURE ENGINEERING
   - Design features that capture different aspects of price action:
     * Momentum: returns over various lookback periods (1d, 5d, 20d)
     * Volatility: rolling std, ATR, bollinger band width
     * Mean reversion: distance from moving averages, RSI, z-scores
     * Volume: volume changes, volume moving averages
     * Patterns: recent candle patterns, support/resistance breaks

   - Consider:
     * Normalize/standardize features for ML models
     * Time-series cross-validation (walk-forward) - don't use future info
     * Feature importance analysis to remove irrelevant features

2. MODEL SELECTION
   - Start with simple models for interpretability:
     * Logistic Regression (baseline, interpretable)
     * Decision Trees/Random Forest (captures non-linear relationships)
     * Gradient Boosting (XGBoost, LightGBM) - often best performance

   - Avoid complex models initially:
     * Neural networks tend to overfit on limited market data
     * Ensemble methods are more robust than single models

3. TRAINING APPROACH
   - Maximize data but avoid lookahead bias:
     * Use 70-80% for training, 20-30% for validation
     * Walk-forward validation: train on period T, test on T+1
     * Don't use future prices in features

   - Class imbalance handling:
     * Markets spend more time up than down (upward bias)
     * Use stratified cross-validation and consider class weights
     * Balance training dataset if severely imbalanced

4. LABEL CREATION
   - Define positively/negatively:
     * Simple: if return_next_period > threshold: label=1 else: label=-1
     * Threshold-based: small moves are neutral (label=0)
     * Risk-adjusted: label based on risk-adjusted returns

   - Target window:
     * What forward period? (1-day, 5-day, 20-day predictions?)
     * Longer windows → slower signals but more stable
     * Shorter windows → faster reactions but noisier

5. BACKTESTING CONSIDERATIONS
   - Prediction confidence:
     * Don't trade on borderline predictions (confidence < 60%)
     * Scale position size with prediction confidence

   - Retraining frequency:
     * Retrain model regularly (monthly/quarterly) - markets change
     * Monitor feature importance over time
     * A/B test new models before switching

6. OVERFITTING WARNING
   - Common pitfalls:
     * Using future data in features → artificially high backtests
     * Parameter-fitting on test set → poor live performance
     * Neglecting transaction costs → backtest looks better than reality

   - Validation:
     * Out-of-sample testing essential
     * Check if model predicts on random data (should be ~50%)
     * Compare backtest vs live trading results (if possible)

7. CODE STRUCTURE
   - Create a feature engineering function:
     * Takes DataFrame + timestamp, returns feature vector
     * No lookahead bias

   - Model interface:
     * predict(features) → returns 1 / -1 / 0
     * predict_proba(features) → returns confidence

   - Integration with strategy:
     * compute_factors: engineer all features
     * on_event: get latest features, call model, return signal

NEXT STEPS:
===========
1. Design features capturing your edge
2. Collect/load training data
3. Label targets and train model
4. Implement feature engineering in compute_factors()
5. Use trained model in on_event()
"""
import pandas as pd
import numpy as np
from ..base_strategy import Strategy
from ...core_logic.events.base_event import Event
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from factors.volatility import ATR, VolatilityFactor
from factors.price_based import Returns, MovingAverage

def build_features(data: pd.DataFrame) -> pd.DataFrame:
    """
    Transform raw OHLCV data into ML features.
    Uses only past data at each row — no lookahead.
    """
    df = data.copy()

    # Momentum (how fast is price moving?)
    df['ret_1d']  = df['Close'].pct_change(1)
    df['ret_5d']  = df['Close'].pct_change(5)
    df['ret_20d'] = df['Close'].pct_change(20)

    # Overnight gap (Open vs previous Close)
    df['gap'] = (df['Open'] - df['Close'].shift(1)) / df['Close'].shift(1)

    # Volatility — uses High/Low
    df['atr']    = (df['High'] - df['Low']) / df['Close']
    df['vol_20d'] = df['ret_1d'].rolling(20).std()

    # Mean reversion (how far is price from its average?)
    df['ma20']        = df['Close'].rolling(20).mean()
    df['dist_from_ma'] = (df['Close'] - df['ma20']) / df['ma20']

    # Volume momentum
    df['vol_ratio'] = df['Volume'] / df['Volume'].rolling(20).mean()

    # Target: will price be higher tomorrow? (1 = yes, 0 = no)
    # shift(-1) means "next row's close" — only used for training, not live
    df['target'] = (df['Close'].shift(-1) > df['Close']).astype(int)

    df.dropna(inplace=True)
    return df


FEATURE_COLS = [
    'ret_1d', 'ret_5d', 'ret_20d',
    'gap', 'atr', 'vol_20d',
    'dist_from_ma', 'vol_ratio',
]

def train_model(data: pd.DataFrame) -> xgb.XGBClassifier:
    """
    Train an XGBoost classifier on historical data.
    Uses a time-ordered split — never random — to prevent lookahead.
    """
    df = build_features(data)

    X = df[FEATURE_COLS].iloc[:-1]   # drop last row: no valid target yet
    y = df['target'].iloc[:-1]

    # Time-ordered split (80% train, 20% test)
    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    model = xgb.XGBClassifier(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=3,
        subsample=0.8,
        random_state=42,
        eval_metric='logloss',
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    print(f"Out-of-sample accuracy: {accuracy_score(y_test, preds):.3f}")
    print("(~0.50 is random chance — anything above is a potential edge)")

    return model


class DirectionalPrediction(Strategy):
    
    CONFIDENCE_THRESHOLD = 0.60   # only trade if model is at least 60% confident

    """ML-based direction prediction strategy template.

    TODO: Implement once ML model is trained.
    """
    def __init__(self, data, model=None):
        """
        Args:
            data: DataFrame with OHLCV data
            model: Trained sklearn/xgboost model with predict() method
            feature_engineer: Function that takes (data, timestamp) and returns features
        """
        super().__init__(data)
        self.features_df = build_features(data)

        if model is None:
            print("No model provided — training on supplied data...")
            self.model = train_model(data)
        else:
            self.model = model
        

    def compute_factors(self, asset, data):
        """Compute all ML features.

        TODO: Implement feature engineering here.
        Should create columns in data for all features used by model.
        """
        # Example of what this should do:
        # data['momentum_1d'] = data['close'].pct_change(1)
        # data['momentum_5d'] = data['close'].pct_change(5)
        # data['volatility'] = data['close'].pct_change().rolling(20).std()
        # data['rsi'] = compute_rsi(data['close'])
        # ... etc
        pass

    def on_event(self, event: Event, positions=None):
        t = event.timestamp

        # Get the feature row for this timestamp
        if t not in self.features_df.index:
            return 0

        features = self.features_df.loc[t, FEATURE_COLS].values.reshape(1, -1)

        # predict_proba returns [[prob_down, prob_up]]
        proba = self.model.predict_proba(features)[0]
        confidence = proba.max()
        prediction = self.model.predict(features)[0]   # 1 = up, 0 = down

        # Skip borderline predictions
        if confidence < self.CONFIDENCE_THRESHOLD:
            return 0

        return 1 if prediction == 1 else -1
