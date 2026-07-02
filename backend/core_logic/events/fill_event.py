from base_event import Event

class FillEvent(Event):
    def __init__(self, timestamp, price, quantity):
        super().__init__("FILL")
        self.timestamp = timestamp
        self.price = price
        self.quantity = quantity