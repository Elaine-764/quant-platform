from core_logic.events.base_event import Event
from strategies.enhancements.signal_types import SignalType
from core_logic.events.signal_event import SignalEvent, FullSignalEvent

class Strategy:
    def __init__(self, data, enhancements):
        self.data = data
        self.enhancements = enhancements
        self.portfolio_positions = None  # Track only positions, not the full portfolio object

    def compute_factors(self, asset):
        raise NotImplementedError

    def on_event(self, event: Event, positions=None):
        raise NotImplementedError

    def get_signals(self, event: Event) -> list[FullSignalEvent]:
        """
        Get signal from strategy with enhancements applied.

        Enhancements can modify the signal through filters and risk controls.
        Order of operations:
        1. Get base signal from strategy
        2. Apply filters (volatility, momentum, volume)
        3. Apply risk controls (stop loss, max position size)
        4. Adjust position size

        Returns:
            signal (int): -1, 0, or 1
            position_size (float): 1.0 by default, modified by position sizing enhancements
        """
        positions = self.portfolio_positions
        try:
            base_signal = self.on_event(event, positions)
        except TypeError:
            base_signal = self.on_event(event)

        def process_single(raw_sig):
            # raw_sig may be int or SignalEvent
            if isinstance(raw_sig, SignalEvent):
                asset = raw_sig.asset
                num = raw_sig.signal
            else:
                asset = getattr(self, 'asset', None)
                num = raw_sig

            # classify into SignalType
            sig_type = self.get_signaltype(num, asset, positions)

            # apply filters and risk controls
            if self.enhancements:
                if 'filters' in self.enhancements:
                    sig_type = self.enhancements['filters'].apply(sig_type, event, self.data, positions)

            # determine position sizing
            position_size = 1.0
            if self.enhancements and 'position_sizing' in self.enhancements and sig_type != SignalType.NO_TRADE:
                sizer = self.enhancements['position_sizing']
                try:
                    position_size = sizer.calculate(sig_type, event, self.data, positions)
                except Exception:
                    try:
                        position_size = sizer.size(sig_type, event, self.data, positions, limit=1)
                    except Exception:
                        position_size = 1.0
            final_event = FullSignalEvent(event.timestamp, asset, sig_type, position_size)

            return final_event

        # If multiple signals returned, process each and return list
        if isinstance(base_signal, (list, tuple)):
            processed = [process_single(s) for s in base_signal]
            return processed

        # Single signal
        processed_event = process_single(base_signal)
        return [processed_event]

    def update_portfolio_state(self, positions):
        """Called by engine to update the current position map for strategies/enhancements."""
        self.portfolio_positions = positions
    
    def get_signaltype(self, signal, asset, positions=None):
        if signal == 0:
            return SignalType.NO_TRADE
        if positions and asset in positions:
            if positions.get(asset, 0) >= 0:
                return SignalType.OPEN_LONG if signal > 0 else SignalType.CLOSE_LONG
            else:
                return SignalType.CLOSE_SHORT if signal > 0 else SignalType.OPEN_SHORT
        return SignalType.OPEN_LONG if signal > 0 else SignalType.OPEN_SHORT
    