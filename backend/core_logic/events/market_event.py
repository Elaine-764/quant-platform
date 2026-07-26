from .base_event import Event

class MarketEvent(Event):
    def __init__(self, timestamp, prices: dict[str, float], volume=None):
        super().__init__("MARKET")
        self.timestamp = timestamp
        self.prices = prices
        self.volume = volume