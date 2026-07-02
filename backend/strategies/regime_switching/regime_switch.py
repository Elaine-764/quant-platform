from ..base_strategy import Strategy
from ...core_logic.events.base_event import Event
# from ...factors.volatility import VolatilityFactor
import numpy as np
from ...core_logic.events.signal_event import SignalEvent
from hmmlearn import hmm

# TODO: check this implementation of hmm

class RegimeSwitching(Strategy):
    """Regime-switching strategy that adapts to market conditions.

    Switches between mean reversion and momentum strategies based on
    volatility regime. In high volatility → mean reversion.
    In low volatility → momentum.
    """
    def __init__(self, data, asset, mean_reversion_strategy, momentum_strategy,
                 vol_window=20, vol_threshold=0.015):
        """
        Args:
            data: DataFrame with OHLCV data
            mean_reversion_strategy: Strategy to use in high volatility regime
            momentum_strategy: Strategy to use in low volatility regime
            vol_window: Window for volatility calculation
            vol_threshold: Volatility threshold for regime switch (annualized)
        """
        super().__init__(data)
        self.asset = asset
        self.mean_reversion_strategy = mean_reversion_strategy
        self.momentum_strategy = momentum_strategy
        self.vol_window = vol_window
        self.vol_threshold = vol_threshold
        self.current_regime = None
        self.feature = None # Format features into a 2D array for the HMM model
        self.hmm_model = None
        self.bull_state = None 

    def compute_factors(self):
        """Compute both strategies' factors and volatility."""
        # Compute factors for both strategies
        self.mean_reversion_strategy.compute_factors()
        self.momentum_strategy.compute_factors()

        self.data['returns'] = np.log(self.data['Close'] / self.data['Close'].shift(1))
        # Pre-compute volatility for regime detection
        self.data['volatility'] = self.data['Returns'].rolling(window=20).std()
        self.data.dropna(inplace=True)

        self.features = self.data[['returns', 'volatility']].values
        self.model = hmm.GaussianHMM(n_components=2, covariance_type="full", n_iter=100, random_state=42)
        self.model.fit(self.features)

        self.data['regime'] = self.model.predict(self.features)

        # Determine which regime is safer by checking average volatility
        state_0_vol = self.data[self.data['regime'] == 0]['volatility'].mean()
        state_1_vol = self.data[self.data['regime'] == 1]['volatility'].mean()

        # Identify the low-volatility (Bull) state
        self.bull_state = 0 if state_0_vol < state_1_vol else 1


    def get_current_regime(self, t):
        """Determine current volatility regime."""
        if t < self.vol_window:
            return 'neutral'

        vol = self.data['volatility'].iloc[t]

        if vol > self.vol_threshold:
            return 'high_vol'
        else:
            return 'low_vol'

    def on_event(self, event: Event):
        t = event.timestamp

        if t < self.vol_window:
            return SignalEvent(t, self.asset, 0)

        regime = self.data['regime'].iloc[t]
        self.current_regime = regime

        # Use mean reversion in high volatility regime -- i.e. bear market
        if regime != self.bull_state:
            return self.mean_reversion_strategy.on_event(event)
        # Use momentum in low volatility regime
        else:
            return self.momentum_strategy.on_event(event)
