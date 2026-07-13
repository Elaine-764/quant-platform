from .base_event import Event

class OrderEvent(Event):
    def __init__(self, timestamp, asset, price, quantity, direction: str, cost):
        super().__init__("ORDER")
        self.timestamp = timestamp
        self.asset = asset,
        self.price = price
        self.quantity = quantity
        self.direction = direction
        self.cost = cost