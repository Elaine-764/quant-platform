import numpy as np
import pandas as pd
import scipy.stats as si
from strategies.base_strategy import Strategy
from core_logic.events.base_event import Event
from core_logic.events.market_event import MarketEvent
from core_logic.events.signal_event import SignalEvent
import pandas as pd

class DeltaHedging(Strategy):
    def __init__(self, data: pd.DataFrame, enhancements, asset: str, strike: float, days_to_expiry: int,
                 r: float = 0.04, assumed_vol: float = None,
                 cash_balance: float = 0.0):
        """
        Parameters
        ----------
        data            : OHLCV DataFrame with at minimum a 'close' column
        asset           : ticker string (informational)
        strike          : option strike price K
        days_to_expiry  : number of trading days until expiry
        r               : risk-free rate (annualised, continuous)
        assumed_vol     : implied vol to use; if None, calibrated from data
        cash_balance    : starting cash (premium collected is added on Day 0)
        """
        data = data.rename(columns={"Close": f"{asset}_Close"})
        super().__init__(data, enhancements)
        self.asset           = asset
        self.strike          = strike
        self.days_to_expiry  = days_to_expiry
        self.r               = r
        self.assumed_vol     = assumed_vol      # None → calibrated in compute_factors
        self.cash_balance    = cash_balance

        # populated by compute_factors / on_event
        self.calibrated_vol  = None
        self.smile_df        = None

    # ------------------------------------------------------------------
    # BSM engine + Greeks
    # ------------------------------------------------------------------
    def bsm(self, S: float, K: float, T: float, r: float,
            sigma: float, q: float = 0.0) -> dict:
        """
        Black-Scholes-Merton prices and the 5 primary Greeks.
        q : continuous dividend yield.
        """
        if T <= 0 or sigma <= 0:
            return {
                "Call_Price":  max(S - K, 0),
                "Put_Price":   max(K - S, 0),
                "Delta_Call":  1.0 if S > K else 0.0,
                "Delta_Put":  -1.0 if K > S else 0.0,
                "Gamma": 0.0, "Vega": 0.0,
                "Theta_Call": 0.0, "Theta_Put": 0.0,
                "Rho_Call":   0.0, "Rho_Put":   0.0,
            }

        # print(f'K = {K}, S = {S}, r = {r}, q = {q}, sigma = {sigma}, T = {T}')
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        N_d1        = si.norm.cdf(d1);  N_minus_d1 = si.norm.cdf(-d1)
        N_d2        = si.norm.cdf(d2);  N_minus_d2 = si.norm.cdf(-d2)
        n_prime_d1  = si.norm.pdf(d1)

        call_price = S * np.exp(-q * T) * N_d1 - K * np.exp(-r * T) * N_d2
        put_price  = K * np.exp(-r * T) * N_minus_d2 - S * np.exp(-q * T) * N_minus_d1

        delta_call = np.exp(-q * T) * N_d1
        delta_put  = -np.exp(-q * T) * N_minus_d1

        gamma = (n_prime_d1 * np.exp(-q * T)) / (S * sigma * np.sqrt(T))
        vega  = S * np.exp(-q * T) * np.sqrt(T) * n_prime_d1

        theta_call = (
            -(S * n_prime_d1 * sigma * np.exp(-q * T)) / (2 * np.sqrt(T))
            - r * K * np.exp(-r * T) * N_d2
            + q * S * np.exp(-q * T) * N_d1
        )
        theta_put = (
            -(S * n_prime_d1 * sigma * np.exp(-q * T)) / (2 * np.sqrt(T))
            + r * K * np.exp(-r * T) * N_minus_d2
            - q * S * np.exp(-q * T) * N_minus_d1
        )

        rho_call = K * T * np.exp(-r * T) * N_d2
        rho_put  = -K * T * np.exp(-r * T) * N_minus_d2

        return {
            "Call_Price":  call_price,
            "Put_Price":   put_price,
            "Delta_Call":  delta_call,
            "Delta_Put":   delta_put,
            "Gamma":       gamma,
            "Theta_Call":  theta_call / 365,    # daily decay
            "Theta_Put":   theta_put / 365,
            "Vega":        vega / 100,           # per 1% vol move
            "Rho_Call":    rho_call / 100,       # per 1% rate move
            "Rho_Put":     rho_put  / 100,
        }

    # ------------------------------------------------------------------
    # Volatility calibration
    # ------------------------------------------------------------------
    def calculate_historical_volatility(self, close_prices: pd.Series,
                                         trading_days: int = 252) -> float:
        log_returns = np.log(close_prices / close_prices.shift(1)).dropna()
        return log_returns.std() * np.sqrt(trading_days)

    # ------------------------------------------------------------------
    # Volatility smile
    # ------------------------------------------------------------------
    def generate_synthetic_smile(self, current_stock_price: float,
                                  base_vol: float = 0.20,
                                  T: float = 30 / 365) -> pd.DataFrame:
        """
        Smile where IV increases 0.4% for every 1% OTM/ITM distance from spot.
        """
        strikes = np.linspace(current_stock_price * 0.8,
                              current_stock_price * 1.2, 9)
        rows = []
        for K in strikes:
            pct_distance = abs(K - current_stock_price) / current_stock_price
            iv = base_vol + pct_distance * 0.4
            greeks = self.bsm(S=current_stock_price, K=K, T=T, r=self.r, sigma=iv)
            rows.append({
                "Strike":       round(K, 2),
                "Synthetic_IV": round(iv * 100, 2),
                "Call_Price":   round(greeks["Call_Price"], 2),
                "Delta_Call":   round(greeks["Delta_Call"], 2),
            })
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # compute_factors  (called once before the event loop)
    # ------------------------------------------------------------------
    def compute_factors(self):
        close = self.data[f"{self.asset}_Close"]

        self.calibrated_vol = self.calculate_historical_volatility(close)
        vol = self.assumed_vol if self.assumed_vol is not None else self.calibrated_vol

        dt = 1 / 252
        records = []

        for i in range(len(close)):
            price = close.iloc[i]
            # bound by days_to_expiry, not total_bars
            T_remaining = max((self.days_to_expiry - i) * dt, 0)

            if price is None or (isinstance(price, float) and np.isnan(price)):
                records.append({col: np.nan for col in [
                    "Call_Price", "Put_Price", "Delta_Call", "Delta_Put",
                    "Gamma", "Theta_Call", "Theta_Put", "Vega", "Rho_Call", "Rho_Put"
                ]})
            else:
                records.append(self.bsm(S=price, K=self.strike,
                                        T=T_remaining, r=self.r, sigma=vol))

        greeks_df = pd.DataFrame(records, index=self.data.index)

        collisions = set(greeks_df.columns) & set(self.data.columns)
        assert not collisions, f"Column collision between Greeks and OHLCV: {collisions}"

        self.data = pd.concat([self.data, greeks_df], axis=1)
        self.smile_df = self.generate_synthetic_smile(
            current_stock_price=close.iloc[0],
            base_vol=vol
        )

        # store the index→bar mapping so on_event can look up integer position
        self._timestamp_to_bar = {ts: i for i, ts in enumerate(self.data.index)}


    def on_event(self, event: Event, positions: dict[str, float] = None) -> SignalEvent | None:
        if event.type != 'MARKET':
            raise ValueError("Incorrect event type.")

        timestamp = event.timestamp
        price     = event.prices.get(self.asset)
        dt        = 1 / 252
        vol       = self.assumed_vol if self.assumed_vol is not None else self.calibrated_vol

        if price is None or (isinstance(price, float) and np.isnan(price)):
            # print(f"[DeltaHedging] WARNING: no price for '{self.asset}' at {timestamp}, skipping.")
            return [SignalEvent(timestamp=timestamp, asset=self.asset, signal=0)]

        bar_index = self._timestamp_to_bar.get(timestamp)
        if bar_index is None:
            # print(f"[DeltaHedging] WARNING: timestamp {timestamp} not in data index, skipping.")
            return [SignalEvent(timestamp=timestamp, asset=self.asset, signal=0)]

        if bar_index >= self.days_to_expiry:
            return [SignalEvent(timestamp=timestamp, asset=self.asset, signal=0)]

        T_remaining      = max((self.days_to_expiry - bar_index) * dt, 0)
        greeks           = self.bsm(S=price, K=self.strike, T=T_remaining, r=self.r, sigma=vol)
        target_delta     = greeks["Delta_Call"]
        current_position = positions.get(self.asset, 0.0) if positions else 0.0
        shares_to_trade  = target_delta - current_position

        if shares_to_trade > 0:
            signal = 1
        elif shares_to_trade < 0:
            signal = -1
        else:
            signal = 0

        return [SignalEvent(timestamp=timestamp, asset=self.asset, signal=signal)]