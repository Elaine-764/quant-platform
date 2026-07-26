from strategies.base_strategy import Strategy
from core_logic.events.base_event import Event
from core_logic.events.signal_event import SignalEvent
import numpy as np
import pandas as pd


class EquitiesBondsDynamic(Strategy):
    """Cross-asset strategy balancing equities vs bonds.

    Adjusts equity exposure based on relative strength and bond yields.
    When bonds are rising (attractive), reduce equity risk.
    When VIX is high, shift to bonds for safety.
    """
    def __init__(self, data, enhancements, eq_data, bonds_data, equity, bond, lookback=20, bond_momentum_window=10):
        eq_data = eq_data.rename(columns={
            "High": f'{equity}_High',
            'Low': f'{equity}_Low',
            'Open': f'{equity}_Open',
            'Close': f'{equity}_Close',
            'Volume': f'{equity}_Volume'
            })
        bonds_data = bonds_data.rename(columns={
            "High": f'{bond}_High',
            'Low': f'{bond}_Low',
            'Open': f'{bond}_Open',
            'Close': f'{bond}_Close',
            'Volume': f'{bond}_Volume'
            })
        from pathlib import Path
        DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
        vix_data = pd.read_csv(f'{DATA_DIR}/^VIX.csv')
        vix = 'VIX'
        vix_data = vix_data.rename(columns={
            "High": f'{vix}_High',
            'Low': f'{vix}_Low',
            'Open': f'{vix}_Open',
            'Close': f'{vix}_Close',
            'Volume': f'{vix}_Volume'
            })
        data = pd.merge(eq_data, bonds_data, on='Date')
        data = pd.merge(data, vix_data, on='Date')

        super().__init__(data, enhancements)
        self.equity = equity
        self.bond = bond
        self.vix = vix
        self.equity_column = f'{equity}_Close'
        self.bond_column = f'{bond}_Close'
        self.vix_column = f'{vix}_Close'
        self.lookback = lookback
        self.bond_momentum_window = bond_momentum_window
        self.asset = equity

        # Tells the engine which columns to pull into MarketEvent.prices for this strategy
        self.price_columns = [self.equity_column, self.bond_column, self.vix_column]

    def compute_factors(self):
        """Pre-compute relative strength and momentum indicators."""
        if self.equity_column in self.data.columns:
            self.data['equity_ret'] = self.data[self.equity_column].pct_change(self.lookback)
        else:
            self.data['equity_ret'] = self.data['Close'].pct_change(self.lookback)

        if self.bond_column in self.data.columns:
            self.data['bond_mom'] = self.data[self.bond_column].pct_change(self.bond_momentum_window)
        else:
            self.data['bond_mom'] = 0

        self.data['rel_strength'] = self.data['equity_ret'] - self.data['bond_mom'] * 0.5

    def on_event(self, event: Event, positions=None):
        t = event.timestamp

        # Pull everything needed from the event's price dict, not self.data
        equity_price = event.prices.get(self.equity)
        bond_price = event.prices.get(self.bond)
        vix_price = event.prices.get(self.vix)

        if equity_price is None or bond_price is None:
            # Missing price for one of the required assets this tick — no signal.
            return [SignalEvent(t, self.equity, 0), SignalEvent(t, self.bond, 0)]

        if t < max(self.lookback, self.bond_momentum_window):
            return [SignalEvent(t, self.equity, 0), SignalEvent(t, self.bond, 0)]

        # Factors are precomputed series (computed once in compute_factors), still indexed by t
        rel_strength = self.data['rel_strength'].iloc[t]
        bond_mom = self.data['bond_mom'].iloc[t]

        vix_high = vix_price is not None and vix_price > 20

        if rel_strength > 0.02 and not vix_high and bond_mom < 0.01:
            return [SignalEvent(t, self.equity, 1), SignalEvent(t, self.bond, -1)]

        if vix_high or bond_mom > 0.02:
            return [SignalEvent(t, self.equity, -1), SignalEvent(t, self.bond, 1)]

        return [SignalEvent(t, self.equity, 0), SignalEvent(t, self.bond, 0)]


class CrossAssetMomentum(Strategy):
    """Trade the asset group with strongest momentum."""
    def __init__(self, data, enhancements, assets, asset_dfs, lookback=20, rebalance_freq=5):
        super().__init__(data=None, enhancements=enhancements)

        if len(assets) == 0 or len(asset_dfs) == 0 or len(asset_dfs) != len(assets):
            raise ValueError("Asset names and asset dataframes must be of the same length and of lengths more than 0.")

        data = asset_dfs[0].rename(columns={
            "High": f'{assets[0]}_High',
            'Low': f'{assets[0]}_Low',
            'Open': f'{assets[0]}_Open',
            'Close': f'{assets[0]}_Close',
            'Volume': f'{assets[0]}_Volume',
        })
        for i in range(1, len(assets)):
            temp = asset_dfs[i].rename(columns={
                "High": f'{assets[i]}_High',
                'Low': f'{assets[i]}_Low',
                'Open': f'{assets[i]}_Open',
                'Close': f'{assets[i]}_Close',
                'Volume': f'{assets[i]}_Volume',
            })
            data = pd.merge(data, temp, on='Date')  

        self.data = data
        self.assets = assets
        self.lookback = lookback
        self.rebalance_freq = rebalance_freq
        self.last_rebalance = -rebalance_freq
        self.price_columns = list(assets)
    
    def compute_factors(self):
        for asset_name in self.assets:
            close_col = f'{asset_name}_Close'
            if close_col in self.data.columns:
                mom_col = f'{asset_name}_momentum'
                self.data[mom_col] = self.data[close_col].pct_change(self.lookback)

    def on_event(self, event: Event, positions=None):
        t = event.timestamp

        # Prices for every tracked asset, straight from the event
        prices = {asset: event.prices.get(asset) for asset in self.assets}

        if t < self.lookback or any(p is None for p in prices.values()):
            return [SignalEvent(t, asset, 0) for asset in self.assets]

        if (t - self.last_rebalance) < self.rebalance_freq:
            return [SignalEvent(t, asset, 0) for asset in self.assets]

        self.last_rebalance = t

        momentums = {}
        for asset_name in self.assets:
            mom_col = f'{asset_name}_momentum'
            if mom_col in self.data.columns:
                momentums[asset_name] = self.data[mom_col].iloc[t]

        if not momentums:
            return [SignalEvent(t, asset, 0) for asset in self.assets]

        strongest = max(momentums, key=momentums.get)
        strongest_mom = momentums[strongest]
        weakest = min(momentums, key=momentums.get)
        weakest_mom = momentums[weakest]

        if strongest_mom > 0:
            return [SignalEvent(t, strongest, 1), SignalEvent(t, weakest, -1)]
        elif strongest_mom < -0.02:
            return [SignalEvent(t, strongest, -1), SignalEvent(t, weakest, 1)]

        return [SignalEvent(t, asset, 0) for asset in self.assets]

class RelativeValueStrategy(Strategy):
    """Trade spread between two assets based on mean reversion."""
    def __init__(self, data, enhancements, asset1, asset2, asset1_data, asset2_data,
                 window=60, threshold=1.5, hedge_ratio=None):
        super().__init__(data=None, enhancements=enhancements)
        asset1_data = asset1_data.rename(columns={
                "High": f'{asset1}_High',
                'Low': f'{asset1}_Low',
                'Open': f'{asset1}_Open',
                'Close': f'{asset1}_Close',
                'Volume': f'{asset1}_Volume'
                }
            )
        asset2_data = asset2_data.rename(columns={
                "High": f'{asset2}_High',
                'Low': f'{asset2}_Low',
                'Open': f'{asset2}_Open',
                'Close': f'{asset2}_Close',
                'Volume': f'{asset2}_Volume'
                }
            )
        self.data = pd.merge(asset1_data, asset2_data, on='Date')
        self.asset1 = asset1
        self.asset2 = asset2
        self.window = window
        self.threshold = threshold
        self.hedge_ratio = hedge_ratio

    def compute_factors(self):
        price1 = self.data[f'{self.asset1}_Close']
        price2 = self.data[f'{self.asset2}_Close']

        if self.hedge_ratio is None:
            ratio = price1.std() / price2.std() * price1.corr(price2)
            self.hedge_ratio = np.clip(ratio, 0.1, 10)
        else:
            self.hedge_ratio = float(self.hedge_ratio)

        norm_price1 = price1 / price1.iloc[0]
        norm_price2 = price2 / price2.iloc[0]

        self.data['cross_spread'] = norm_price1 - (self.hedge_ratio * norm_price2)
        self.data['cross_spread_mean'] = self.data['cross_spread'].rolling(self.window).mean()
        self.data['cross_spread_std'] = self.data['cross_spread'].rolling(self.window).std()

    def on_event(self, event: Event, positions=None):
        t = event.timestamp

        price1 = event.prices.get(self.asset1)
        price2 = event.prices.get(self.asset2)

        if t < self.window or price1 is None or price2 is None:
            return [SignalEvent(t, self.asset1, 0), SignalEvent(t, self.asset2, 0)]

        spread = self.data['cross_spread'].iloc[t]
        mean = self.data['cross_spread_mean'].iloc[t]
        std = self.data['cross_spread_std'].iloc[t]

        if std == 0 or np.isnan(std):
            return [SignalEvent(t, self.asset1, 0), SignalEvent(t, self.asset2, 0)]

        z_score = (spread - mean) / std

        if z_score < -self.threshold:
            return [SignalEvent(t, self.asset1, 1), SignalEvent(t, self.asset2, -1)]

        if z_score > self.threshold:
            return [SignalEvent(t, self.asset1, -1), SignalEvent(t, self.asset2, 1)]

        return [SignalEvent(t, self.asset1, 0), SignalEvent(t, self.asset2, 0)]