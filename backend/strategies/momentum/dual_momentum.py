from base_strategy import Strategy
from core_logic.events.base_event import Event
import numpy as np
from core_logic.events.signal_event import SignalEvent

class DualMomentum(Strategy):
    """Dual Momentum strategy combining relative and absolute momentum.

    Relative momentum: asset performance relative to benchmark
    Absolute momentum: asset performance relative to risk-free rate

    Only trades long when both are positive, avoids markets in downtrends.
    """
    def __init__(self, data, asset, lookback=20, benchmark_column=None, risk_free_rate=0.0):
        """
        Args:
            data: DataFrame with OHLCV data
            lookback: Number of periods for momentum calculation
            benchmark_column: Column name for benchmark (e.g., 'SPY'). If None, uses close.
            risk_free_rate: Annual risk-free rate for absolute momentum calculation
        """
        super().__init__(data)
        self.asset = asset
        self.lookback = lookback
        self.benchmark_column = benchmark_column
        self.risk_free_rate = risk_free_rate / 252 if risk_free_rate > 0 else 0

    def compute_factors(self):
        """Pre-compute momentum metrics."""
        # Absolute momentum: asset returns
        self.data['abs_momentum'] = self.data['Close'].pct_change(self.lookback)

        # Relative momentum: asset returns minus benchmark returns
        if self.benchmark_column and self.benchmark_column in self.data.columns:
            benchmark_returns = self.data[self.benchmark_column].pct_change(self.lookback)
            self.data['rel_momentum'] = self.data['abs_momentum'] - benchmark_returns
        else:
            # If no benchmark, use risk-free rate as comparison
            self.data['rel_momentum'] = self.data['abs_momentum'] - (self.risk_free_rate * self.lookback)

        self.asset = self.asset

    def on_event(self, event: Event, positions=None):
        t = event.timestamp

        if t < self.lookback:
            return SignalEvent(t, self.asset, 0)

        abs_mom = self.data['abs_momentum'].iloc[t]
        rel_mom = self.data['rel_momentum'].iloc[t]

        # Only go long if BOTH momentum types are positive
        if abs_mom > 0 and rel_mom > 0:
            return SignalEvent(t, self.asset, 1)
        # Go short only if both are significantly negative
        elif abs_mom < -0.02 and rel_mom < -0.02:  # -2% threshold
            return SignalEvent(t, self.asset, -1)

        return SignalEvent(t, self.asset, 0)
