from core_logic.events.base_event import Event
from strategies.enhancements.signal_types import SignalType
class SignalEvent(Event):
    def __init__(self, timestamp, asset, signal: int):
        super().__init__("SIGNAL")
        self.timestamp = timestamp
        self.signal = signal  # +1, -1, 0
        self.asset = asset

class FullSignalEvent(Event):
    def __init__(self, timestamp, asset, signal: SignalType, size):
        super().__init__("FULLSIGNAL")
        self.timestamp = timestamp
        self.signal = signal  # +1, -1, 0
        self.asset = asset
        self.size = size # how much to trade