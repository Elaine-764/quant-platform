from ..base_strategy import Strategy
from ...core_logic.events.base_event import Event
from ...core_logic.events.signal_event import SignalEvent
from ...core_logic.events.market_event import MarketEvent
import numpy as np
import pandas as pd
import statsmodels.api as sm

'''
TODO: implement Ornstein-Uhlenbeck process
1. find asset's rolling z-score based on moving average and std
2. calibrate OU regression on Z-score rather than the price
    -> get the reversion speed (\theta) and half-life
3. Trade rule
    - based on half life
    - based on zscore
'''

class ZScoreReversion(Strategy):
    """Mean reversion strategy using an OU-calibrated Z-score.

    Buy when price is below -threshold z-score, sell when above +threshold.
    """
    def __init__(self, data, asset, window=20, threshold=2.0):
        super().__init__(data)
        self.asset = asset
        self.window = window
        self.threshold = threshold
        self.half_life = None

    def estimate_ou_parameters(self, subset):
        """
        Calibrates an OU process from a discretized AR(1) fit:
        y(t) = a + b*y(t-1) + epsilon(t)

        Returns None if the fit doesn't imply mean reversion (b outside (0, 1)).
        """
        X = subset.shift(1).dropna()
        Y = subset.loc[X.index]
        X = sm.add_constant(X)

        model = sm.OLS(Y, X)
        results = model.fit()

        const = results.params.iloc[0]
        b = results.params.iloc[1]
        var_eps = results.mse_resid

        # b = exp(-theta*dt); only valid (mean-reverting) for 0 < b < 1
        if not (0 < b < 1) or np.isnan(b):
            return None

        theta = -np.log(b)               # speed of mean reversion
        mu = const / (1 - b)              # long-run mean
        sigma = np.sqrt(var_eps * 2 * theta / (1 - b**2))
        half_life = np.log(2) / theta

        return mu, theta, sigma, half_life

    def compute_factors(self):
        """Pre-compute a simple rolling mean/std, mainly for diagnostics —
        the actual trading signal uses the OU-calibrated mean/std computed
        per-bar in on_event, not these."""
        self.data['z_mean'] = self.data['Close'].rolling(window=self.window).mean()
        self.data['z_std'] = self.data['Close'].rolling(window=self.window).std(ddof=1)

    def on_event(self, event: Event):
        t = event.timestamp
        if t < self.window:
            return SignalEvent(t, self.asset, 0)

        # Use the live price if this is a MarketEvent, otherwise fall back
        # to the last known historical close (t-1, to avoid lookahead bias)
        if isinstance(event, MarketEvent):
            current_price = event.price
        else:
            current_price = self.data['Close'].iloc[t - 1]

        subset = self.data['Close'].iloc[t - self.window: t]
        ou_params = self.estimate_ou_parameters(subset)

        if ou_params is None:
            # Fit implies no mean reversion over this window — stay flat
            return SignalEvent(t, self.asset, 0)

        # NOTE: recalibration every time may be expensive
        mu, theta, sigma, half_life = ou_params
        self.half_life = half_life  # exposed so the portfolio/execution layer
                                     # can enforce a time-based stop externally

        sigma_eq = sigma / np.sqrt(2 * theta)
        if sigma_eq == 0 or np.isnan(sigma_eq):
            return SignalEvent(t, self.asset, 0)

        z_score = (current_price - mu) / sigma_eq
        self.data.loc[self.data.index[t], 'Z_score'] = z_score

        if z_score <= -self.threshold:
            return SignalEvent(t, self.asset, 1)
        elif z_score >= self.threshold:
            return SignalEvent(t, self.asset, -1)

        return SignalEvent(t, self.asset, 0)