from base_strategy import Strategy
from core_logic.events.base_event import Event
from core_logic.events.signal_event import SignalEvent
import numpy as np
import pandas as pd
from functools import reduce
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.vector_ar.vecm import coint_johansen


class PairsTrading(Strategy):
    """Pairs trading strategy using spread mean reversion.

    Identifies two (or more) correlated assets and trades the spread when
    it deviates from its historical mean. Assumes each input DataFrame has
    OHLCV columns plus a 'Date' column to merge on.
    """

    def __init__(self, data_dfs: list[pd.DataFrame], assets: list[str], window=60, threshold=2.0, hedge_ratio=None):
        """
        Args:
            data_dfs: list of DataFrames, one per asset (OHLCV + 'Date')
            assets: asset names, matching the order of data_dfs
            window: rolling window for mean/std calculation
            threshold: Z-score threshold for entry/exit signals
            hedge_ratio: weight for asset2 relative to asset1 (auto-calculated
                if None). Only used by the base two-asset strategy;
                EngleGranger/Johansen derive their own.
        """
        if len(data_dfs) != len(assets) or len(data_dfs) == 0:
            raise ValueError('The numbers of datasets and asset names do not match, or you did not provide any dataframes/asset names.')

        renamed_dfs = []
        for df, asset in zip(data_dfs, assets):
            renamed_dfs.append(df.rename(columns={
                "High": f'{asset}_High',
                'Low': f'{asset}_Low',
                'Open': f'{asset}_Open',
                'Close': f'{asset}_Close',
                'Volume': f'{asset}_Volume',
            }))

        data = reduce(lambda left, right: pd.merge(left, right, on='Date'), renamed_dfs)
        data = data.sort_values('Date').reset_index(drop=True)

        super().__init__(data)
        self.assets = assets
        self.window = window
        self.threshold = threshold
        self.hedge_ratio = hedge_ratio

    def _close_col(self, asset):
        col = f'{asset}_Close'
        return col if col in self.data.columns else 'Close'

    def compute_factors(self):
        """Pre-compute spread and its rolling statistics for the two-asset case."""
        if len(self.assets) != 2:
            raise NotImplementedError(
                "Base PairsTrading.compute_factors only supports exactly two "
                "assets; use EngleGranger or Johansen for N-asset/cointegration spreads."
            )

        asset1, asset2 = self.assets
        price1 = self.data[self._close_col(asset1)]
        price2 = self.data[self._close_col(asset2)]

        if self.hedge_ratio is None:
            correlation = price1.corr(price2)
            ratio_of_std = price1.std() / price2.std()
            self.hedge_ratio = ratio_of_std * correlation
        else:
            self.hedge_ratio = max(0.1, min(10, self.hedge_ratio))

        self.data['spread'] = price1 - (self.hedge_ratio * price2)
        self.data['spread_mean'] = self.data['spread'].rolling(window=self.window).mean()
        self.data['spread_std'] = self.data['spread'].rolling(window=self.window).std(ddof=1)

    def on_event(self, event: Event, positions=None):
        t = event.timestamp
        asset1, asset2 = self.assets

        if t < self.window or 'spread' not in self.data.columns:
            return [SignalEvent(t, asset1, 0), SignalEvent(t, asset2, 0)]

        spread = self.data['spread'].iloc[t]
        mean = self.data['spread_mean'].iloc[t]
        std = self.data['spread_std'].iloc[t]

        if std == 0 or np.isnan(std):
            return [SignalEvent(t, asset1, 0), SignalEvent(t, asset2, 0)]

        z_score = (spread - mean) / std

        if z_score <= -self.threshold:
            return [SignalEvent(t, asset1, 1), SignalEvent(t, asset2, -1)]
        elif z_score >= self.threshold:
            return [SignalEvent(t, asset1, -1), SignalEvent(t, asset2, 1)]

        return [SignalEvent(t, asset1, 0), SignalEvent(t, asset2, 0)]


class EngleGranger(PairsTrading):
    """Pairs trading using the Engle-Granger two-step cointegration test to
    derive the hedge ratio and validate mean-reversion before trading."""

    def __init__(self, data_dfs, assets, window=60, threshold=2, hedge_ratio=None):
        if len(data_dfs) != 2 or len(assets) != 2:
            raise ValueError("Please enter exactly two dataframes and two asset names.")
        super().__init__(data_dfs, assets, window, threshold, hedge_ratio)
        self.cointegration_result = None

    @staticmethod
    def engle_granger_spread(asset_y, asset_x):
        """
        Implements the Engle-Granger two-step cointegration test.
        Returns the hedge ratio, intercept, residual spread, and ADF p-value.
        """
        X = sm.add_constant(asset_x)
        model = sm.OLS(asset_y, X).fit()

        alpha = model.params.iloc[0]
        gamma = model.params.iloc[1]  # hedge ratio

        spread = asset_y - (alpha + gamma * asset_x)

        adf_result = adfuller(spread, maxlag=None, regression='c')
        p_value = adf_result[1]

        return {
            'hedge_ratio': gamma,
            'intercept': alpha,
            'spread': spread,
            'adf_p_value': p_value,
            'is_cointegrated': p_value < 0.05,
        }

    def compute_factors(self):
        asset_y_name, asset_x_name = self.assets
        asset_y = self.data[self._close_col(asset_y_name)]
        asset_x = self.data[self._close_col(asset_x_name)]

        result = self.engle_granger_spread(asset_y, asset_x)
        self.cointegration_result = result
        self.hedge_ratio = result['hedge_ratio']

        self.data['spread'] = result['spread']
        self.data['spread_mean'] = self.data['spread'].rolling(window=self.window).mean()
        self.data['spread_std'] = self.data['spread'].rolling(window=self.window).std(ddof=1)

    def on_event(self, event: Event, positions=None):
        t = event.timestamp
        asset_y, asset_x = self.assets

        if (self.cointegration_result is None
                or not self.cointegration_result['is_cointegrated']
                or t < self.window
                or 'spread' not in self.data.columns):
            return [SignalEvent(t, asset_y, 0), SignalEvent(t, asset_x, 0)]

        spread = self.data['spread'].iloc[t]
        mean = self.data['spread_mean'].iloc[t]
        std = self.data['spread_std'].iloc[t]

        if std == 0 or np.isnan(std):
            return [SignalEvent(t, asset_y, 0), SignalEvent(t, asset_x, 0)]

        z_score = (spread - mean) / std

        if z_score <= -self.threshold:
            return [SignalEvent(t, asset_y, 1), SignalEvent(t, asset_x, -1)]
        elif z_score >= self.threshold:
            return [SignalEvent(t, asset_y, -1), SignalEvent(t, asset_x, 1)]

        return [SignalEvent(t, asset_y, 0), SignalEvent(t, asset_x, 0)]


class Johansen(PairsTrading):
    """Pairs/basket trading using the Johansen cointegration test, which
    generalizes to N >= 2 assets and finds the cointegration rank directly."""

    def __init__(self, data_dfs, assets, window=60, threshold=2, hedge_ratio=None, confidence_level=95):
        if len(data_dfs) < 2 or len(assets) < 2:
            raise ValueError("Please enter at least two dataframes and two asset names.")
        super().__init__(data_dfs, assets, window, threshold, hedge_ratio)
        self.confidence_level = confidence_level
        self.johansen_result = None

    def generalized_johansen_strategy(self):
        """
        Performs the Johansen cointegration test for N >= 2 assets.
        Finds the cointegration rank and returns the optimal portfolio weights.

        Confidence level choices: 90, 95, or 99.
        """
        conf_map = {90: 0, 95: 1, 99: 2}
        col_idx = conf_map.get(self.confidence_level, 1)

        price_cols = [self._close_col(asset) for asset in self.assets]
        price_data = self.data[price_cols].dropna()

        jres = coint_johansen(price_data, det_order=0, k_ar_diff=1)

        trace_stats = jres.lr1
        crit_vals = jres.cvt[:, col_idx]

        num_assets = price_data.shape[1]  # number of series, not rows

        cointegration_rank = 0
        for r in range(num_assets):
            if trace_stats[r] > crit_vals[r]:
                cointegration_rank += 1
            else:
                break

        is_cointegrated = cointegration_rank > 0

        raw_weights = jres.evec[:, 0]
        normalized_weights = raw_weights / raw_weights[0]

        portfolio_spread = pd.Series(
            np.dot(price_data.values, normalized_weights),
            index=price_data.index,
        )

        result = {
            'is_cointegrated': is_cointegrated,
            'cointegration_rank': cointegration_rank,
            'trace_statistics': trace_stats,
            'critical_values': crit_vals,
            'weights': normalized_weights,
            'portfolio_spread': portfolio_spread,
        }
        self.johansen_result = result
        return result

    def compute_factors(self):
        result = self.generalized_johansen_strategy()

        self.data['spread'] = result['portfolio_spread']
        self.data['spread_mean'] = self.data['spread'].rolling(window=self.window).mean()
        self.data['spread_std'] = self.data['spread'].rolling(window=self.window).std(ddof=1)

    def on_event(self, event: Event, positions=None):
        t = event.timestamp

        if (self.johansen_result is None
                or not self.johansen_result['is_cointegrated']
                or t < self.window
                or 'spread' not in self.data.columns):
            return [SignalEvent(t, asset, 0) for asset in self.assets]

        spread = self.data['spread'].iloc[t]
        mean = self.data['spread_mean'].iloc[t]
        std = self.data['spread_std'].iloc[t]

        if std == 0 or np.isnan(std):
            return [SignalEvent(t, asset, 0) for asset in self.assets]

        z_score = (spread - mean) / std
        weights = self.johansen_result['weights']

        if z_score <= -self.threshold:
            direction = 1
        elif z_score >= self.threshold:
            direction = -1
        else:
            return [SignalEvent(t, asset, 0) for asset in self.assets]

        # A positive weight means that leg moves with the portfolio spread,
        # so it takes the opposite side of a negative-weight leg.
        signals = []
        for asset, weight in zip(self.assets, weights):
            side = direction if weight > 0 else -direction
            signals.append(SignalEvent(t, asset, side))
        return signals