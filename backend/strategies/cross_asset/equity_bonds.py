from ..base_strategy import Strategy
from ...core_logic.events.base_event import Event
from ...core_logic.events.signal_event import SignalEvent
import numpy as np
import pandas as pd

class EquitiesBondsDynamic(Strategy):
    """Cross-asset strategy balancing equities vs bonds.

    Adjusts equity exposure based on relative strength and bond yields.
    When bonds are rising (attractive), reduce equity risk.
    When VIX is high, shift to bonds for safety.
    """
    def __init__(self, eq_data, bonds_data, equity, bond, lookback=20, bond_momentum_window=10):
        """
        Args:
            data: DataFrame with OHLCV data for both assets
            equity_column: Column name for equity prices
            bond_column: Column name for bond prices
            vix_column: Optional VIX column for volatility regime
            lookback: Period for relative strength calculation
            bond_momentum_window: Window for bond momentum
        """
        eq_data = eq_data.rename(columns={
            "High": f'{equity}_High',
            'Low': f'{equity}_Low',
            'Open': f'{equity}_Open',
            'Close': f'{equity}_Close',
            'Volume': f'{equity}_Volume'
            })
        bonds_data= bonds_data.rename(columns={
            "High": f'{bond}_High',
            'Low': f'{bond}_Low',
            'Open': f'{bond}_Open',
            'Close': f'{bond}_Close',
            'Volume': f'{bond}_Volume'
            })
        vix_data = pd.read_csv('../../data/processed/^VIX.csv')
        vix = 'VIX'
        vix_data= vix_data.rename(columns={
            "High": f'{vix}_High',
            'Low': f'{vix}_Low',
            'Open': f'{vix}_Open',
            'Close': f'{vix}_Close',
            'Volume': f'{vix}_Volume'
            })
        data = pd.merge(eq_data, bonds_data, on='Date')
        data = pd.merge(data, vix_data, on='Date')
        
        super().__init__(data)

        self.equity_column = f'{equity}_Close'
        self.bond_column = f'{bond}_Close'
        self.vix_column = f'{vix}_Close'
        self.lookback = lookback
        self.bond_momentum_window = bond_momentum_window
        self.asset = equity

    def compute_factors(self):
        """Pre-compute relative strength and momentum indicators."""
        # Equity returns
        if self.equity_column in self.data.columns:
            self.data['equity_ret'] = self.data[self.equity_column].pct_change(self.lookback)
        else:
            self.data['equity_ret'] = self.data['close'].pct_change(self.lookback)

        # Bond momentum (attractive rising bonds mean safety)
        if self.bond_column in self.data.columns:
            self.data['bond_mom'] = self.data[self.bond_column].pct_change(self.bond_momentum_window)
        else:
            self.data['bond_mom'] = 0

        # Relative strength: equity momentum vs bond momentum
        self.data['rel_strength'] = self.data['equity_ret'] - self.data['bond_mom'] * 0.5

        self.asset = self.asset

    def on_event(self, event: Event):
        t = event.timestamp

        if t < max(self.lookback, self.bond_momentum_window):
            return [SignalEvent(t, self.equity_column, 0), SignalEvent(t, self.bond_column, 0)]

        rel_strength = self.data['rel_strength'].iloc[t]
        bond_mom = self.data['bond_mom'].iloc[t]

        # High VIX (if available) shifts toward bonds
        vix_high = False
        if self.vix_column and self.vix_column in self.data.columns:
            vix_value = self.data[self.vix_column].iloc[t]
            vix_high = vix_value > 20  # Elevated VIX threshold

        # Overweight equities: positive relative strength + non-elevated VIX
        if rel_strength > 0.02 and not vix_high and bond_mom < 0.01:
            return [SignalEvent(t, self.equity_column, 1), SignalEvent(t, self.bond_column, -1)]

        # Overweight bonds: bond momentum strong or VIX high
        if vix_high or bond_mom > 0.02:
            return [SignalEvent(t, self.equity_column, -1), SignalEvent(t, self.bond_column, 1)]

        return [SignalEvent(t, self.equity_column, 0), SignalEvent(t, self.bond_column, 0)]


class CrossAssetMomentum(Strategy):
    """Trade the asset group with strongest momentum.

    Compares momentum across multiple asset classes and trades the
    strongest performer while shorting the weakest.
    """
    def __init__(self, data, assets, lookback=20, rebalance_freq=5):
        """
        Args:
            data: DataFrame containing multiple asset prices
            assets: List of column names for different assets
            lookback: Period for momentum calculation
            rebalance_freq: Periods between rebalancing
        """
        super().__init__(data)
        self.assets = assets
        self.lookback = lookback
        self.rebalance_freq = rebalance_freq
        self.last_rebalance = -rebalance_freq

    def compute_factors(self, asset, data):
        """Pre-compute momentum for all assets."""
        for asset_name in self.assets:
            if asset_name in data.columns:
                col_name = f'{asset_name}_momentum'
                data[col_name] = data[asset_name].pct_change(self.lookback)
        self.asset = asset

    def on_event(self, event: Event):
        t = event.timestamp

        if t < self.lookback:
            return [SignalEvent(t, getattr(self, 'asset', None), 0)]

        # Only rebalance at specified intervals
        if (t - self.last_rebalance) < self.rebalance_freq:
            return [SignalEvent(t, getattr(self, 'asset', None), 0)]

        self.last_rebalance = t

        # Calculate momentum for each asset
        momentums = {}
        for asset_name in self.assets:
            col_name = f'{asset_name}_momentum'
            if col_name in self.data.columns:
                momentums[asset_name] = self.data[col_name].iloc[t]

        if not momentums:
            return [SignalEvent(t, getattr(self, 'asset', None), 0)]

        # Find strongest and weakest
        strongest = max(momentums, key=momentums.get)
        strongest_mom = momentums[strongest]

        # Buy strongest momentum, sell weakest
        weakest = min(momentums, key=momentums.get)
        weakest_mom = momentums[weakest]

        if strongest_mom > 0:
            return [SignalEvent(t, strongest, 1), SignalEvent(t, weakest, -1)]
        elif strongest_mom < -0.02:
            return [SignalEvent(t, strongest, -1), SignalEvent(t, weakest, 1)]

        return [SignalEvent(t, getattr(self, 'asset', None), 0)]


class RelativeValueStrategy(Strategy):
    """Trade spread between two assets based on mean reversion.

    When one asset significantly outperforms, expect reversion.
    Similar to pairs trading but for cross-asset classes.
    """
    def __init__(self, data, asset1_column, asset2_column,
                 window=60, threshold=1.5, hedge_ratio=None):
        """
        Args:
            data: DataFrame with both asset prices
            asset1_column: Column for first asset
            asset2_column: Column for second asset
            window: Period for mean/std calculation
            threshold: Z-score threshold for signals
            hedge_ratio: Relative weighting (auto-calculated if None)
        """
        super().__init__(data)
        self.asset1_column = asset1_column
        self.asset2_column = asset2_column
        self.window = window
        self.threshold = threshold
        self.hedge_ratio = hedge_ratio

    def compute_factors(self, asset, data):
        """Pre-compute spread and statistics."""
        price1 = data[self.asset1_column]
        price2 = data[self.asset2_column]

        # Calculate hedge ratio
        if self.hedge_ratio is None:
            ratio = price1.std() / price2.std() * price1.corr(price2)
            self.hedge_ratio = np.clip(ratio, 0.1, 10)
        else:
            self.hedge_ratio = float(self.hedge_ratio)

        # Normalize prices to comparable scale
        norm_price1 = price1 / price1.iloc[0]
        norm_price2 = price2 / price2.iloc[0]

        # Calculate spread
        data['cross_spread'] = norm_price1 - (self.hedge_ratio * norm_price2)
        data['cross_spread_mean'] = data['cross_spread'].rolling(self.window).mean()
        data['cross_spread_std'] = data['cross_spread'].rolling(self.window).std()

        self.asset = asset

    def on_event(self, event: Event):
        t = event.timestamp

        if t < self.window:
            return [SignalEvent(t, self.asset1_column, 0), SignalEvent(t, self.asset2_column, 0)]

        spread = self.data['cross_spread'].iloc[t]
        mean = self.data['cross_spread_mean'].iloc[t]
        std = self.data['cross_spread_std'].iloc[t]

        if std == 0 or np.isnan(std):
            return [SignalEvent(t, self.asset1_column, 0), SignalEvent(t, self.asset2_column, 0)]

        z_score = (spread - mean) / std

        # Buy when spread is low (asset1 cheap vs asset2)
        if z_score < -self.threshold:
            return [SignalEvent(t, self.asset1_column, 1), SignalEvent(t, self.asset2_column, -1)]

        # Sell when spread is high (asset1 expensive vs asset2)
        if z_score > self.threshold:
            return [SignalEvent(t, self.asset1_column, -1), SignalEvent(t, self.asset2_column, 1)]

        return [SignalEvent(t, self.asset1_column, 0), SignalEvent(t, self.asset2_column, 0)]
