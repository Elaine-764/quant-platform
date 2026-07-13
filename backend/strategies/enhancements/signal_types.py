from enum import Enum

class SignalType(Enum):
    OPEN_LONG   =  1
    OPEN_SHORT  = -1
    CLOSE_LONG  =  2   # always allowed through
    CLOSE_SHORT = -2   # always allowed through
    NO_TRADE    =  0

def classify_signal(raw_signal: float, current_pos: int) -> SignalType:
    """Classify signal relative to current position."""
    if raw_signal > 0:
        if current_pos < 0:
            return SignalType.CLOSE_SHORT   # closing, always allow
        else:
            return SignalType.OPEN_LONG     # opening/adding, can be blocked
    elif raw_signal < 0:
        if current_pos > 0:
            return SignalType.CLOSE_LONG    # closing, always allow
        else:
            return SignalType.OPEN_SHORT    # opening/adding, can be blocked
    return SignalType.NO_TRADE