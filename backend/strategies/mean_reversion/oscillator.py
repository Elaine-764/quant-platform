from base_strategy import Strategy
from core_logic.events.base_event import Event
from core_logic.events.signal_event import SignalEvent
from factors.price_based import RSI

class OscillatorMeanReversion(Strategy):
    """Mean reversion strategy using RSI (Relative Strength Index).

    Buy when RSI < 30 (oversold), sell when RSI > 70 (overbought).
    """
    def __init__(self, data, enhancements, asset, window=14, buy_threshold=30, sell_threshold=70):
        super().__init__(data, enhancements)
        self.window = window
        self.asset = asset
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def compute_factors(self):
        """Compute RSI factor."""
        rsi = RSI(asset=self.asset, window=self.window)
        rsi.compute(self.data)
        self.rsi_column = rsi.output_column()
        self.asset = self.asset

    def on_event(self, event: Event, positions=None):
        t = event.timestamp

        if t < self.window:
            return SignalEvent(t, self.asset, 0)

        rsi_value = self.data[self.rsi_column].iloc[t]

        # Buy signal: RSI < 30 (oversold condition)
        if rsi_value < self.buy_threshold:
            return SignalEvent(t, self.asset, 1)
        # Sell signal: RSI > 70 (overbought condition)
        elif rsi_value > self.sell_threshold:
            return SignalEvent(t, self.asset, -1)

        return SignalEvent(t, self.asset, 0)
