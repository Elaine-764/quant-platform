from base_strategy import Strategy
from core_logic.events.base_event import Event
from core_logic.events.signal_event import SignalEvent

class MAToMACrossover(Strategy):
    """MA Crossover momentum strategy.

    Buy when short MA > long MA (bullish crossover), sell when short MA < long MA.
    """
    def __init__(self, data, asset, short_window=20, long_window=50):
        super().__init__(data)
        self.asset = asset
        self.short_window = short_window
        self.long_window = long_window

    def compute_factors(self):
        """Pre-compute moving averages."""
        self.data['short_ma'] = self.data['Close'].rolling(window=self.short_window).mean()
        self.data['long_ma'] = self.data['Close'].rolling(window=self.long_window).mean()
        self.asset = self.asset

    def on_event(self, event: Event, positions=None):
        t = event.timestamp

        if t < self.long_window:
            return SignalEvent(t, self.asset, 0)

        short_ma = self.data['short_ma'].iloc[t]
        long_ma = self.data['long_ma'].iloc[t]

        # Buy signal: short MA above long MA (uptrend)
        if short_ma > long_ma:
            return SignalEvent(t, self.asset, 1)
        # Sell signal: short MA below long MA (downtrend)
        elif short_ma < long_ma:
            return SignalEvent(t, self.asset, -1)

        return SignalEvent(t, self.asset, 0)