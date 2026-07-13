import numpy as np
import pandas as pd
import scipy.stats as si
from ..base_strategy import Strategy


class DeltaHedging(Strategy):
    def __init__(self, data, asset: str, strike: float, days_to_expiry: int,
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
        super().__init__(data)
        self.asset           = asset
        self.strike          = strike
        self.days_to_expiry  = days_to_expiry
        self.r               = r
        self.assumed_vol     = assumed_vol      # None → calibrated in compute_factors
        self.cash_balance    = cash_balance
        self.shares_held     = 0.0

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
        """
        Calibrates volatility from the full price history, attaches the smile
        DataFrame, and stamps both onto self.data so the engine can pass them
        through history if desired.
        """
        close = self.data["close"]

        self.calibrated_vol = self.calculate_historical_volatility(close)

        # Use caller-supplied vol if provided, else fall back to calibrated
        vol = self.assumed_vol if self.assumed_vol is not None else self.calibrated_vol

        # Pre-compute BSM columns for every bar (useful for factor inspection)
        total_bars = len(self.data)
        dt = 1 / 252

        records = []
        for i, price in enumerate(close):
            T_remaining = max((total_bars - i) * dt, 0)
            greeks = self.bsm(S=price, K=self.strike, T=T_remaining,
                              r=self.r, sigma=vol)
            records.append(greeks)

        greeks_df = pd.DataFrame(records, index=self.data.index)
        self.data = pd.concat([self.data, greeks_df], axis=1)

        # Smile snapshot at current spot
        self.smile_df = self.generate_synthetic_smile(
            current_stock_price=close.iloc[0],
            base_vol=vol
        )

    # ------------------------------------------------------------------
    # on_event  (called by the engine on every bar)
    # ------------------------------------------------------------------
    def on_event(self, event: dict):
        """
        Dynamic delta-hedging rebalance on each new price bar.

        event keys expected from BacktestEngine:
            timestamp, bar_index, price (close), portfolio_state
        """
        t     = event["bar_index"]
        price = event["price"]
        total_bars = len(self.data)
        dt = 1 / 252

        vol = self.assumed_vol if self.assumed_vol is not None else self.calibrated_vol

        if t == 0:
            # --- Day 0: sell the call, collect premium, establish initial hedge ---
            T0 = total_bars * dt
            greeks = self.bsm(S=price, K=self.strike, T=T0, r=self.r, sigma=vol)

            self.cash_balance += greeks["Call_Price"]       # collect premium
            self.shares_held   = greeks["Delta_Call"]
            self.cash_balance -= self.shares_held * price   # buy initial hedge

        else:
            # --- Day t: rebalance to new delta ---
            T_remaining = max((total_bars - t) * dt, 0)
            greeks = self.bsm(S=price, K=self.strike,
                              T=T_remaining, r=self.r, sigma=vol)

            target_shares  = greeks["Delta_Call"]
            shares_to_trade = target_shares - self.shares_held

            self.cash_balance -= shares_to_trade * price    # buy/sell difference
            self.shares_held   = target_shares
            self.cash_balance *= np.exp(self.r * dt)        # risk-free growth

        # Update portfolio state so the engine can record it
        if self.portfolio_state is not None:
            self.portfolio_state["shares_held"]  = self.shares_held
            self.portfolio_state["cash_balance"] = self.cash_balance
            self.portfolio_state["hedge_pnl"]    = (
                self.cash_balance
                + self.shares_held * price
                - max(price - self.strike, 0)
            )