from base_strategy import Strategy
from core_logic.events.base_event import Event
from core_logic.events.signal_event import SignalEvent

class PriceMomentum(Strategy):
    """Price Momentum strategy.

    Buy when recent returns are positive (upward momentum), sell when negative.
    Based on short-term price changes over a lookback period.
    """
    def __init__(self, data, asset, lookback=20, threshold=0.0):
        """
        Args:
            data: DataFrame with OHLCV data
            lookback: Number of periods for momentum calculation
            threshold: Return threshold for signals (default: 0% break-even)
        """
        super().__init__(data)
        self.asset = asset
        self.lookback = lookback
        self.threshold = threshold

    def compute_factors(self):
        """Pre-compute momentum (returns)."""
        self.data['momentum'] = self.data['Close'].pct_change(self.lookback) * 100  # Convert to percentage
        self.asset = self.asset

    def on_event(self, event: Event, positions=None):
        t = event.timestamp

        if t < self.lookback:
            return SignalEvent(t, self.asset, 0)

        momentum = self.data['momentum'].iloc[t]

        # Buy signal: momentum above threshold (positive momentum)
        if momentum > self.threshold:
            return SignalEvent(t, self.asset, 1)
        # Sell signal: momentum below negative threshold
        elif momentum < -self.threshold:
            return SignalEvent(t, self.asset, -1)

        return SignalEvent(t, self.asset, 0)
