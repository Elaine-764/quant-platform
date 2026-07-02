from .base_event import Event

class MarketEvent(Event):
    def __init__(self, timestamp, price, volume=None):
        super().__init__("MARKET")
        self.timestamp = timestamp
        self.price = price
        self.volume = volume