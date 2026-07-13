"""Strategy filters to modify signals based on market conditions."""
import numpy as np
from ...strategies.enhancements.signal_types import SignalType

class Filter:
    def apply(self, signal_type, event, data) -> SignalType:
        raise NotImplementedError

    def is_closing(self, signal_type: SignalType, portfolio_state) -> bool:
        return signal_type in (SignalType.CLOSE_LONG, SignalType.CLOSE_SHORT)

class VolatilityFilter(Filter):
    """Filter signals based on volatility levels.

    Disables trading when volatility is too high/low, useful for avoiding
    choppy markets or staying in favorable regimes.
    """
    def __init__(self, lookback=20, min_volatility=None, max_volatility=None):
        """
        Args:
            lookback: Period for volatility calculation
            min_volatility: Disable trading if vol below this (e.g., 0.005 for 0.5%)
            max_volatility: Disable trading if vol above this (e.g., 0.03 for 3%)
        """
        self.lookback = lookback
        self.min_volatility = min_volatility
        self.max_volatility = max_volatility

    def apply(self, signal_type, event, data, portfolio_state) -> SignalType:
        # Always allow closing trades
        if self.is_closing(signal_type):
            return signal_type
        if signal_type == SignalType.NO_TRADE:
            return signal_type
        t = event.timestamp
        if t < self.window:
            return SignalType.NO_TRADE  # not enough data → don't open

        section = data['Close'].iloc[t - self.lookback : t + 1]
        returns = section.pct_change()
        vol = float(np.std(returns))

        if vol > self.max_vol or vol < self.min_vol:
            return SignalType.NO_TRADE  # block opening

        return signal_type


class MomentumFilter(Filter):
    """Filter signals based on momentum alignment.

    Only trades when short-term momentum aligns with the signal direction.
    """
    def __init__(self, lookback=5):
        """
        Args:
            lookback: Period for momentum confirmation
        """
        self.lookback = lookback

    def apply(self, signal_type, event, data, portfolio_state) -> SignalType:
        if self.is_closing(signal_type):
            return signal_type
        if signal_type == SignalType.NO_TRADE:
            return signal_type
        
        t = event.timestamp
        if t < self.lookback:
            return SignalType.NO_TRADE

        # Calculate momentum (returns over lookback)
        current_price = data['Close'].iloc[t]
        past_price = data['Close'].iloc[t - self.lookback]
        momentum = (current_price - past_price) / past_price

        # Buy signal should have positive momentum
        if signal_type == SignalType.OPEN_LONG and momentum < 0:
            return SignalType.CLOSE_LONG

        # Sell signal should have negative momentum
        if signal_type == SignalType.OPEN_SHORT and momentum > 0:
            return SignalType.CLOSE_SHORT

        return signal_type


class VolumeFilter(Filter):
    """Filter signals based on volume.

    Ensures sufficient volume for signal to be reliable; avoids illiquid moves.
    """
    def __init__(self, lookback=20, min_volume_ratio=0.8):
        """
        Args:
            lookback: Period for average volume calculation
            min_volume_ratio: Require current volume >= ratio * average volume
        """
        self.lookback = lookback
        self.min_volume_ratio = min_volume_ratio

    def apply(self, signal_type, event, data, portfolio_state) -> SignalType:
        if self.is_closing(signal_type):
            return signal_type
        if signal_type == SignalType.NO_TRADE:
            return signal_type

        t = event.timestamp
        if t < self.lookback or 'Volume' not in data.columns:
            return SignalType.NO_TRADE

        current_volume = data['Volume'].iloc[t]
        avg_volume = data['Volume'].iloc[t - self.lookback:t].mean()

        if current_volume < self.min_volume_ratio * avg_volume:
            return SignalType.NO_TRADE

        return signal_type


class StopLoss(Filter):
    """Stop loss control - exit if price drops below threshold.

    Automatically closes losing positions to limit downside.
    """
    def __init__(self, stop_loss_pct=0.02):
        """
        Args:
            stop_loss_pct: Stop loss level as percentage from entry (e.g., 0.02 = 2%)
        """
        self.stop_loss_pct = stop_loss_pct
    
    def apply(self, signal_type, event, data, portfolio_state) -> SignalType:
        if not portfolio_state or signal_type == SignalType.NO_TRADE or not hasattr(portfolio_state, 'current_position'):
            return signal_type
    
        pos = portfolio_state.current_position
        if pos and pos.get('entry_price'):
            current_price = data['Close'].iloc[event.timestamp]
            loss_pct = (current_price - pos['entry_price']) / pos['entry_price']

            # Force exit if stop loss triggered
            if loss_pct < -self.stop_loss_pct:
                return SignalType.CLOSE_LONG if pos.get('direction', 1) > 0 else SignalType.CLOSE_SHORT
        return signal_type

    
class MaxPositionSize(Filter):
    """Limit position size relative to portfolio.

    Prevents over-leveraging and ensures proper position sizing.
    """
    def __init__(self, max_position_pct=0.05):
        """
        Args:
            max_position_pct: Max position size as % of portfolio (e.g., 0.05 = 5%)
        """
        self.max_position_pct = max_position_pct

    def apply(self, signal_type, event, data, portfolio_state) -> SignalType:
        if self.is_closing(signal_type) or not portfolio_state or signal_type == SignalType.NO_TRADE:
            return signal_type  # always allow exits or no trades
        
        current_price = data['close'].iloc[event.timestamp]
        position_value = 0

        if hasattr(portfolio_state, 'current_position') and portfolio_state.current_position:
            position_value = portfolio_state.current_position.get('quantity', 0) * current_price

        max_position_value = portfolio_state.equity * self.max_position_pct

        # If already at max position, don't add more
        if abs(position_value) >= max_position_value:
            return SignalType.NO_TRADE  # circuit breaker tripped

        return signal_type
    

class MaxDrawdownControl(Filter):
    """Disable trading if portfolio has hit max drawdown.

    Circuit breaker to stop trading during severe drawdowns.
    """
    def __init__(self, max_drawdown_pct=0.15):
        """
        Args:
            max_drawdown_pct: Max acceptable drawdown as percentage (e.g., 0.15 = 15%)
        """
        self.max_drawdown_pct = max_drawdown_pct

    def apply(self, signal_type, event, data, portfolio_state) -> SignalType:
        if signal_type == SignalType.NO_TRADE or not portfolio_state:
            return signal_type 
        
        # Calculate current drawdown
        equity = portfolio_state.equity
        peak_equity = max(portfolio_state.equity_curve)
        drawdown = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0

        if drawdown > self.max_drawdown_pct:
            return SignalType.NO_TRADE  # Disable all signals during severe drawdown

        return signal_type

class ConsecutiveLossControl(Filter):
    """Disable trading after consecutive losses.

    Protects against continued bad execution or adverse conditions.
    """
    def __init__(self, max_consecutive_losses=3):
        """
        Args:
            max_consecutive_losses: Number of losses before disabling trades
        """
        self.max_consecutive_losses = max_consecutive_losses

    def apply(self, signal_type, event, data, portfolio_state) -> SignalType:
        if signal_type == SignalType.NO_TRADE or not portfolio_state or not hasattr(portfolio_state, 'trade_history'):
            return signal_type  # always allow exits
        
        consecutive_losses = 0
        for trade in reversed(portfolio_state.trade_history):
            if trade.get('pnl', 0) < 0:
                consecutive_losses += 1
            else:
                break

        if consecutive_losses >= self.max_consecutive_losses:
            return SignalType.NO_TRADE

        return signal_type
    

class TimeBasedControl(Filter):
    """Prevent trading during certain times or after trading limit.

    Useful for avoiding high-spread hours or preventing overtrading.
    """
    def __init__(self, max_trades_per_day=5, trading_start_hour=9, trading_end_hour=16):
        """
        Args:
            max_trades_per_day: Maximum trades per calendar day
            trading_start_hour: Hour to start trading (24h format)
            trading_end_hour: Hour to end trading (24h format)
        """
        self.max_trades_per_day = max_trades_per_day
        self.trading_start_hour = trading_start_hour
        self.trading_end_hour = trading_end_hour

    def apply(self, signal_type, event, data, portfolio_state) -> SignalType:
        if signal_type == SignalType.NO_TRADE:
            return signal_type

        # Note: Would need datetime info from event
        # This is a template - actual implementation depends on event structure
        # Check if within trading hours and haven't exceeded daily trade limit

        return signal_type
    

class CompositeFilter(Filter):
    """Combine multiple filters - signal is valid only if all pass."""
    def __init__(self, filters):
        self.filters = filters

    def apply(self, signal_type, event, data, portfolio_state) -> SignalType:
        for f in self.filters:
            signal = f.apply(signal_type, event, data, portfolio_state)
            if signal == SignalType.NO_TRADE:
                return SignalType.NO_TRADE
        return signal