from ..base_strategy import Strategy
from ...core_logic.events.base_event import Event
import numpy as np
import pandas as pd
from ...core_logic.events.signal_event import SignalEvent

class CointegrationBased(Strategy):
    """Statistical arbitrage strategy using cointegrated spreads.

    For two cointegrated assets, trades deviations from the long-run
    equilibrium relationship (spread). Assumes cointeg relationship exists.
    """
    def __init__(self, data1, data2, asset1, asset2, window=60, threshold=2.0, beta=None):
        """
        Args:
            data: DataFrame with OHLCV data
            asset1: First asset name (key in data)
            asset2: Second asset name (key in data)
            window: Rolling window for mean/std calculation
            threshold: Z-score threshold for spread deviations
            beta: Cointegration coefficient (regressor coefficient if None: OLS calculated)
        """
        # merge data1 and 2 based on timestamp
        data1 = data1.rename(columns={
            "High": f'{asset1}_High',
            'Low': f'{asset1}_Low',
            'Open': f'{asset1}_Open',
            'Close': f'{asset1}_Close',
            'Volume': f'{asset1}_Volume'
            })
        data2= data2.rename(columns={
            "High": f'{asset2}_High',
            'Low': f'{asset2}_Low',
            'Open': f'{asset2}_Open',
            'Close': f'{asset2}_Close',
            'Volume': f'{asset2}_Volume'
            })
        data = pd.merge(data1, data2, on='Date')
        super().__init__(data)
        self.asset1 = asset1
        self.asset2 = asset2
        self.window = window
        self.threshold = threshold
        self.beta = beta


    def compute_factors(self):
        """Pre-compute cointegrated spread and its statistics."""
        price1 = self.data[f'{self.asset1}_Close'] if f'{self.asset1}_Close' in self.data else self.data['Close']
        price2 = self.data[f'{self.asset2}_Close'] if f'{self.asset2}_Close' in self.data else self.data['Close']

        # Calculate beta (cointegration factor) using rolling OLS if not provided
        if self.beta is None:
            # Simple regression: price1 = alpha + beta * price2
            # Use correlation and std ratio as approximation
            self.beta = price1.corr(price2) * (price1.std() / price2.std())
            self.beta = max(0.1, min(10, self.beta))  # Bound beta to reasonable range
        else:
            self.beta = float(self.beta)

        # Calculate spread: price1 - beta * price2 (residual from cointegration)
        self.data['coint_spread'] = price1 - (self.beta * price2)
        self.data['coint_mean'] = self.data['coint_spread'].rolling(window=self.window).mean()
        self.data['coint_std'] = self.data['coint_spread'].rolling(window=self.window).std(ddof=1)

    def on_event(self, event: Event):
        t = event.timestamp

        if t < self.window:
            return [SignalEvent(t, self.asset1, 0), SignalEvent(t, self.asset2, 0)]

        spread = self.data['coint_spread'].iloc[t]
        mean = self.data['coint_mean'].iloc[t]
        std = self.data['coint_std'].iloc[t]

        if std == 0 or np.isnan(std):
            return [SignalEvent(t, self.asset1, 0), SignalEvent(t, self.asset2, 0)]

        z_score = (spread - mean) / std

        # Buy signal: spread below mean (revert upward)
        # Asset1 cheap relative to equilibrium prediction
        if z_score <= -self.threshold:
            return [SignalEvent(t, self.asset1, 1), SignalEvent(t, self.asset2, -1)]
        # Sell signal: spread above mean (revert downward)
        # Asset1 expensive relative to equilibrium prediction
        elif z_score >= self.threshold:
            return [SignalEvent(t, self.asset1, -1), SignalEvent(t, self.asset2, 1)]

        return [SignalEvent(t, self.asset1, 0), SignalEvent(t, self.asset2, 0)]
