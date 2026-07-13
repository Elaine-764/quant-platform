"""Position sizing methods to adjust trade sizes based on market conditions."""
import numpy as np
from ...strategies.enhancements.signal_types import SignalType
class PositionSizer:
    """
    Converts a signal into an actual order quantity.
    Default: use full remaining capacity.
    Override for fractional sizing.
    """
    def size(self, signal_type: SignalType, event, data, portfolio_state, limit: int, fraction: float = 1.0) -> int:
        pos = portfolio_state.current_position if hasattr(portfolio_state, 'current_position') else 0
        buy_cap  = max(0, limit - pos)
        sell_cap = max(0, limit + pos)

        if signal_type == SignalType.OPEN_LONG:
            return int(buy_cap * fraction)
        elif signal_type == SignalType.OPEN_SHORT:
            return int(sell_cap * fraction)
        elif signal_type == SignalType.CLOSE_LONG:
            return pos  # close entire long
        elif signal_type == SignalType.CLOSE_SHORT:
            return abs(pos)  # close entire short
        return 0

class FractionalSizer(PositionSizer):
    """Use only a fraction of available capacity per trade."""
    def __init__(self, fraction: float = 0.25):
        self.fraction = fraction

    def size(self, signal_type: SignalType, event, data, portfolio_state, limit: int, fraction: float = 1.0) -> int:
        return super().size(self, signal_type, event, data, portfolio_state, limit, fraction)

class VolatilityScaling(PositionSizer):
    """Scale position size inversely with volatility.

    Trade smaller when market is volatile, larger when calm.
    Useful for risk management and smoothing returns.
    """
    def __init__(self, lookback=20, target_volatility=0.015):
        """
        Args:
            lookback: Period for volatility calculation
            target_volatility: Target annualized volatility level (e.g., 0.015 = 1.5%)
        """
        self.lookback = lookback
        self.target_volatility = target_volatility

    def size(self, signal_type: SignalType, event, data, portfolio_state, limit: int, fraction: float = 1.0) -> int:
        t = event.timestamp
        if t < self.lookback:
            return 1.0
    
        returns = data['Close'].pct_change(1).iloc[t - self.lookback + 1:t + 1]
        volatility = returns.std() * np.sqrt(252)

        if volatility == 0:
            return 1.0
    
        position_size = self.target_volatility / volatility
        return np.clip(position_size, 0.1, 3.0)

class KellyCriterion(PositionSizer):
    """Kelly Criterion for optimal position sizing.

    Based on win rate and win/loss ratio to maximize long-term growth.
    Requires portfolio state tracking for profitability metrics.
    """
    def __init__(self, win_rate=0.55, avg_win=0.02, avg_loss=0.01, kelly_fraction=0.25):
        """
        Args:
            win_rate: Historical proportion of winning trades
            avg_win: Average profit per winning trade
            avg_loss: Average loss per losing trade
            kelly_fraction: Fractional Kelly (0.25 = quarter Kelly for safety)
        """
        self.win_rate = win_rate
        self.avg_win = avg_win
        self.avg_loss = avg_loss
        self.kelly_fraction = kelly_fraction
    
    def size(self, signal_type: SignalType, event, data, portfolio_state, limit: int, fraction: float = 1.0) -> int:
        # Kelly formula: f* = (p * b - q) / b
        # where p = win rate, b = ratio of win to loss, q = loss rate
        p = self.win_rate
        q = 1 - p
        b = self.avg_win / self.avg_loss if self.avg_loss > 0 else 1

        kelly = (p * b - q) / b if b > 0 else 0
        kelly = max(0, kelly)  # Never go negative

        # Apply fractional Kelly for safety
        position_size = kelly * self.kelly_fraction

        # Bound to reasonable range [0.05, 2.0]
        return np.clip(position_size, 0.05, 2.0) 
    

# class PositionSizer:
#     """Base position sizing interface."""
#     def calculate(self, signal, event, data, portfolio_state):
#         """Calculate position size multiplier (1.0 = full size)."""
#         raise NotImplementedError


# class FixedPositionSizer(PositionSizer):
#     """Fixed position size - always trade the same amount."""
#     def __init__(self, size=1.0):
#         self.size = size

#     def calculate(self, signal, event, data, portfolio_state):
#         return self.size


# class VolatilityScaling(PositionSizer):
#     """Scale position size inversely with volatility.

#     Trade smaller when market is volatile, larger when calm.
#     Useful for risk management and smoothing returns.
#     """
#     def __init__(self, lookback=20, target_volatility=0.015):
#         """
#         Args:
#             lookback: Period for volatility calculation
#             target_volatility: Target annualized volatility level (e.g., 0.015 = 1.5%)
#         """
#         self.lookback = lookback
#         self.target_volatility = target_volatility

#     def calculate(self, signal, event, data, portfolio_state):
#         t = event.timestamp

#         if t < self.lookback:
#             return 1.0

#         # Calculate rolling volatility
#         returns = data['Close'].pct_change(1).iloc[t - self.lookback + 1:t + 1]
#         volatility = returns.std() * np.sqrt(252)

#         if volatility == 0:
#             return 1.0

#         # Size inversely proportional to volatility
#         position_size = self.target_volatility / volatility
#         # Bound to reasonable range [0.1, 3.0]
#         return np.clip(position_size, 0.1, 3.0)


class DynamicKelly(PositionSizer):
    """Dynamic Kelly based on actual portfolio performance.

    Adapts Kelly criterion based on recent win rate and trade profitability.
    """
    def __init__(self, lookback_trades=20, kelly_fraction=0.25):
        """
        Args:
            lookback_trades: Number of recent trades to analyze
            kelly_fraction: Fractional Kelly for conservative management
        """
        self.lookback_trades = lookback_trades
        self.kelly_fraction = kelly_fraction

    def size(self, signal_type: SignalType, event, data, portfolio_state, limit: int, fraction: float = 1.0) -> int:
        if not portfolio_state or not hasattr(portfolio_state, 'trade_history'):
            return 1.0  # Default to full size if no history

        trades = portfolio_state.trade_history[-self.lookback_trades:]

        if len(trades) < 5:
            return 1.0  # Insufficient history

        # Calculate actual win rate and profit/loss ratios
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]

        if len(losing_trades) == 0:
            return 2.0  # Very good performance, increase position

        win_rate = len(winning_trades) / len(trades) 
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = abs(np.mean([t['pnl'] for t in losing_trades]))

        b = avg_win / avg_loss if avg_loss > 0 else 1
        kelly = (win_rate * b - (1 - win_rate)) / b if b > 0 else 0
        kelly = max(0, kelly)

        position_size = kelly * self.kelly_fraction
        return np.clip(position_size, 0.05, 2.0)
