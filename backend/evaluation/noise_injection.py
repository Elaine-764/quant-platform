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
from core_logic.engine.engine import BacktestEngine


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
        self.asset_columns = self._discover_asset_columns(data)

    def _discover_asset_columns(self, data: pd.DataFrame) -> dict:
        assets = {}
        for col in data.columns:
            for suffix in ("_Open", "_High", "_Low", "_Close"):
                if col.endswith(suffix):
                    asset = col[: -len(suffix)]
                    assets.setdefault(asset, {})[suffix[1:].lower()] = col
        # Only keep assets that have all four OHLC columns present
        return {a: cols for a, cols in assets.items() if {"open", "high", "low", "close"} <= cols.keys()}

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
        """Applies independent OHLC noise to every discovered asset's columns."""
        noisy = clean_data.copy()
        n = len(noisy)

        for asset, cols in self.asset_columns.items():
            open_c, high_c, low_c, close_c = cols["open"], cols["high"], cols["low"], cols["close"]

            local_vol = self._local_vol(noisy[close_c])
            noise_std = local_vol * noisy[close_c] * self.noise_factor

            offset_open  = np.random.normal(0, noise_std, n)
            offset_close = np.random.normal(0, noise_std, n)
            offset_high  = np.abs(np.random.normal(0, noise_std, n))
            offset_low   = np.abs(np.random.normal(0, noise_std, n))

            noisy[open_c]  = noisy[open_c]  + offset_open
            noisy[close_c] = noisy[close_c] + offset_close
            noisy[high_c]  = np.maximum(noisy[open_c], np.maximum(noisy[close_c], noisy[high_c] + offset_high))
            noisy[low_c]   = np.minimum(noisy[open_c], np.minimum(noisy[close_c], noisy[low_c] - offset_low))

            for c in (open_c, high_c, low_c, close_c):
                noisy[c] = noisy[c].clip(lower=1e-8)

        return noisy

    # ------------------------------------------------------------------
    # MonteCarlo hook
    # ------------------------------------------------------------------
    def _run_once(self) -> float:
        noisy_data = self._inject_noise(self.data)
        self.engine.reset_for_new_run(new_data=noisy_data)
        result = self.engine.run()
        return self._compute_metric(result["history"])

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
        self.engine.reset_for_new_run(new_data=noisy_data)
        result = self.engine.run()
        return self._compute_metric(result["history"])

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
