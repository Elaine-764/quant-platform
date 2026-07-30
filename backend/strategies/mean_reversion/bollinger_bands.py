from strategies.base_strategy import Strategy
from core_logic.events.base_event import Event
from factors.price_based import BollingerBands
from core_logic.events.market_event import MarketEvent
from core_logic.events.signal_event import SignalEvent

class BollingerBandsReversion(Strategy):
    """Mean reversion strategy using Bollinger Bands.

    Buy when price touches lower band, sell when price touches upper band.
    """
    def __init__(self, data, enhancements, asset, window=20, num_std=2.0):
        super().__init__(data. enhancements)
        self.asset = asset
        self.window = window
        self.num_std = num_std
        self.bb_factor = None

    def compute_factors(self):
        bb = BollingerBands(self.asset, window=self.window, num_std=self.num_std)
        sma, upper, lower = bb.compute(self.data)
        self.data['bb_sma'] = sma
        self.data['bb_upper'] = upper
        self.data['bb_lower'] = lower

    def on_event(self, event: Event, positions=None):
        t = event.timestamp

        if t < self.window:
            return SignalEvent(t, self.asset, 0)
        
        if isinstance(event, MarketEvent):
            close = event.price
        else:
            close = self.data['Close'].iloc[t]
        upper = self.data['bb_upper'].iloc[t]
        lower = self.data['bb_lower'].iloc[t]

        # Buy signal: price touches lower band
        if close <= lower:
            return SignalEvent(t, self.asset, 1)
        
        # Sell signal: price touches upper band
        elif close >= upper:
            return SignalEvent(t, self.asset, -1)

        return SignalEvent(t, self.asset, 0)
