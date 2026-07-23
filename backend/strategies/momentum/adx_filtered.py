from base_strategy import Strategy
from core_logic.events.base_event import Event
from factors.price_based import ADX
from core_logic.events.signal_event import SignalEvent

class ADXFilteredTrend(Strategy):
    """ADX-filtered trend following strategy.

    Uses ADX (Average Directional Index) to confirm strong trends.
    Only trades when trend is strong (ADX > threshold).
    Uses +DI/-DI to determine trend direction.
    """
    def __init__(self, data, asset, adx_window=14, adx_threshold=25):
        """
        Args:
            data: DataFrame with OHLCV data (requires 'high', 'low', 'close')
            adx_window: ADX calculation period
            adx_threshold: Minimum ADX for trend confirmation (typically 20-30)
        """
        super().__init__(data)
        self.asset = asset
        self.adx_window = adx_window
        self.adx_threshold = adx_threshold

    def compute_factors(self):
        """Compute ADX and directional indicators."""
        adx = ADX(asset=self.asset, window=self.adx_window)
        adx.compute(self.data)
        self.adx_column = adx.output_column()
        self.plus_di_column = f"{self.asset}_plus_di"
        self.minus_di_column = f"{self.asset}_minus_di"
        self.asset = self.asset

    def on_event(self, event: Event, positions=None):
        t = event.timestamp

        if t < self.adx_window:
            return SignalEvent(t, self.asset, 0)

        adx_value = self.data[self.adx_column].iloc[t]
        plus_di = self.data[self.plus_di_column].iloc[t]
        minus_di = self.data[self.minus_di_column].iloc[t]

        # Only trade if ADX is strong (trend is clear)
        if adx_value < self.adx_threshold:
            return SignalEvent(t, self.asset, 0)

        # Buy signal: strong uptrend (+DI > -DI and ADX strong)
        if plus_di > minus_di:
            return SignalEvent(t, self.asset, 1)
        # Sell signal: strong downtrend (-DI > +DI and ADX strong)
        elif minus_di > plus_di:
            return SignalEvent(t, self.asset, -1)

        return SignalEvent(t, self.asset, 0)
