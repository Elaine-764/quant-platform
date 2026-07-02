'''
Noise injection (Advanced Monte Carlo)
Option 1: OHLC Price Bar Distortion: Randomly shifting the open, high, low,
          and close of historicla bars
    Steps
     1. Define limit of random noise
     2. Find the appropriate number of runs `n` (see wikipedia page)
     3. Close hisotrical data for each simulation
     4. Apply the noise function: add a random var (drawn from a Normal distr.) t
        to the price metric of every bar
     5. Re-run strategy on each variable - `n` times in total
Option 2: Slippage and Execution NoiseL randomly penalizing fills or delaying 
          execution times
'''
import numpy as np
import pandas as pd
from monte_carlo import MonteCarlo
from ..core_logic.engine.engine import BacktestEngine


class NoiseInjectionOHLC(MonteCarlo):
    def __init__(self, data, backtest_engine: BacktestEngine,
                 epsilon: float = 0.01, confidence: float = 0.95, k: int = 30,
                 noise_factor: float = 0.05, vol_window: int = 20,
                 metric: str = "sharpe"):
        """
        Parameters
        ----------
        noise_factor : scales injected noise relative to local volatility
                       (e.g. 0.05 = noise is 5% of local vol)
        vol_window   : rolling window (bars) for local volatility estimation
        metric       : scalar metric to extract from each run's history
        """
        super().__init__(data, backtest_engine, epsilon, confidence, k)
        self.noise_factor = noise_factor
        self.vol_window   = vol_window
        self.metric       = metric

        self.all_metrics  = []
        self.final_mean   = None

    # ------------------------------------------------------------------
    # Local volatility: rolling std of close returns, forward-filled
    # ------------------------------------------------------------------
    def _local_vol(self, close: pd.Series) -> pd.Series:
        returns = close.pct_change()
        vol = returns.rolling(self.vol_window, min_periods=1).std()
        return vol.fillna(vol.mean())

    # ------------------------------------------------------------------
    # Metric extraction (same pattern as BCI class)
    # ------------------------------------------------------------------
    def _compute_metric(self, history: list) -> float:
        df = pd.DataFrame(history).set_index("timestamp").sort_index()
        pv = df["portfolio_value"]
        daily_returns = pv.pct_change().dropna()

        if self.metric == "sharpe":
            return 0.0 if daily_returns.std() == 0 else \
                   (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        elif self.metric == "cagr":
            n_years = len(pv) / 252
            return (pv.iloc[-1] / pv.iloc[0]) ** (1 / n_years) - 1
        elif self.metric == "max_drawdown":
            return ((pv - pv.cummax()) / pv.cummax()).min()
        else:
            raise ValueError(f"Unknown metric: {self.metric!r}")

    # ------------------------------------------------------------------
    # Core noise injection
    # ------------------------------------------------------------------
    def _inject_noise(self, clean_data: pd.DataFrame) -> pd.DataFrame:
        """
        For every bar:
          noise_std = local_vol[i] * close[i] * noise_factor   (price-scaled)
          offset_o, offset_c ~ N(0, noise_std)
          After shifting O/C, recompute H/L so OHLC relationships stay valid:
            high  = max(noisy_open, noisy_close, original_high  + offset_h)
            low   = min(noisy_open, noisy_close, original_low   + offset_l)
        """
        noisy = clean_data.copy()
        local_vol = self._local_vol(noisy["close"])

        # price-scaled noise std per bar
        noise_std = local_vol * noisy["close"] * self.noise_factor

        n = len(noisy)
        offset_open  = np.random.normal(0, noise_std, n)
        offset_close = np.random.normal(0, noise_std, n)
        offset_high  = np.abs(np.random.normal(0, noise_std, n))   # high can only go up
        offset_low   = np.abs(np.random.normal(0, noise_std, n))   # low  can only go down

        noisy["open"]  = noisy["open"]  + offset_open
        noisy["close"] = noisy["close"] + offset_close
        noisy["high"]  = np.maximum(noisy["open"], noisy["close"],
                                    noisy["high"] + offset_high)
        noisy["low"]   = np.minimum(noisy["open"], noisy["close"],
                                    noisy["low"]  - offset_low)

        # clip negatives (shouldn't happen with small noise_factor, but be safe)
        for col in ["open", "high", "low", "close"]:
            noisy[col] = noisy[col].clip(lower=1e-8)

        return noisy

    # ------------------------------------------------------------------
    # MonteCarlo hook
    # ------------------------------------------------------------------
    def _run_once(self) -> float:
        noisy_data = self._inject_noise(self.data)
        history    = self.engine.run(noisy_data)
        return self._compute_metric(history)

    # ------------------------------------------------------------------
    # run() — inherits find_n logic, adds metric collection
    # ------------------------------------------------------------------
    def run(self) -> dict:
        self.find_n()
        n = self.n

        metrics = list(self.sample_results)      # reuse k sample runs
        for _ in range(n - self.k):
            metrics.append(self._run_once())

        self.all_metrics = metrics
        self.final_mean  = float(np.mean(metrics))

        alpha = 1 - self.confidence
        return {
            "mean_metric":   self.final_mean,
            "std_metric":    float(np.std(metrics)),
            "ci_lower":      float(np.percentile(metrics, 100 * alpha / 2)),
            "ci_upper":      float(np.percentile(metrics, 100 * (1 - alpha / 2))),
            "n_simulations": n,
        }


# ======================================================================

class NoiseInjectionSlippage(MonteCarlo):
    def __init__(self, data, backtest_engine: BacktestEngine,
                 epsilon: float = 0.01, confidence: float = 0.95, k: int = 30,
                 slippage_pct: float = 0.001, delay_prob: float = 0.1,
                 metric: str = "sharpe"):
        """
        Parameters
        ----------
        slippage_pct : max random fill penalty as fraction of price
                       fill_price = intended_price * (1 ± U[0, slippage_pct])
        delay_prob   : probability that any given order is delayed by 1 bar
        metric       : scalar metric extracted from history
        """
        super().__init__(data, backtest_engine, epsilon, confidence, k)
        self.slippage_pct = slippage_pct
        self.delay_prob   = delay_prob
        self.metric       = metric

        self.all_metrics  = []
        self.final_mean   = None

    # ------------------------------------------------------------------
    # Slippage: perturb the 'close' column used for fill prices
    # Delay:    on delayed bars, replace close[i] with close[i+1] (next bar)
    # ------------------------------------------------------------------
    def _inject_slippage(self, clean_data: pd.DataFrame) -> pd.DataFrame:
        """
        Simulates realistic execution noise:
          - Every bar gets a random fill penalty drawn from U[0, slippage_pct],
            applied as an adverse price move (buys fill higher, sells fill lower;
            here we encode the worst-case by just shifting close adversely by a
            random fraction so the engine sees a degraded fill price).
          - With probability delay_prob the bar's close is replaced by the
            next bar's open (execution missed current bar's close).
        """
        noisy = clean_data.copy()
        n = len(noisy)

        # --- slippage penalty (always adverse: raises effective fill cost) ---
        slip = np.random.uniform(0, self.slippage_pct, n)
        noisy["close"] = noisy["close"] * (1 + slip)

        # --- execution delay: swap close[i] → open[i+1] on delayed bars ---
        delay_mask = np.random.random(n) < self.delay_prob
        delay_mask[-1] = False                       # can't delay the last bar
        delayed_indices = np.where(delay_mask)[0]
        noisy.loc[noisy.index[delayed_indices], "close"] = \
            noisy["open"].iloc[delayed_indices + 1].values

        # OHLC consistency: high must be >= close after slippage
        noisy["high"] = np.maximum(noisy["high"], noisy["close"])

        return noisy

    # ------------------------------------------------------------------
    # Metric extraction (shared pattern)
    # ------------------------------------------------------------------
    def _compute_metric(self, history: list) -> float:
        df = pd.DataFrame(history).set_index("timestamp").sort_index()
        pv = df["portfolio_value"]
        daily_returns = pv.pct_change().dropna()

        if self.metric == "sharpe":
            return 0.0 if daily_returns.std() == 0 else \
                   (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        elif self.metric == "cagr":
            n_years = len(pv) / 252
            return (pv.iloc[-1] / pv.iloc[0]) ** (1 / n_years) - 1
        elif self.metric == "max_drawdown":
            return ((pv - pv.cummax()) / pv.cummax()).min()
        else:
            raise ValueError(f"Unknown metric: {self.metric!r}")

    # ------------------------------------------------------------------
    # MonteCarlo hook
    # ------------------------------------------------------------------
    def _run_once(self) -> float:
        noisy_data = self._inject_slippage(self.data)
        history    = self.engine.run(noisy_data)
        return self._compute_metric(history)

    # ------------------------------------------------------------------
    # run()
    # ------------------------------------------------------------------
    def run(self) -> dict:
        self.find_n()
        n = self.n

        metrics = list(self.sample_results)
        for _ in range(n - self.k):
            metrics.append(self._run_once())

        self.all_metrics = metrics
        self.final_mean  = float(np.mean(metrics))

        alpha = 1 - self.confidence
        return {
            "mean_metric":   self.final_mean,
            "std_metric":    float(np.std(metrics)),
            "ci_lower":      float(np.percentile(metrics, 100 * alpha / 2)),
            "ci_upper":      float(np.percentile(metrics, 100 * (1 - alpha / 2))),
            "n_simulations": n,
        }
