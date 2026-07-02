'''
Bootstrapped confidence intervals (Fundamental Monte Carlo)
- to provent overfitting to historical data
Steps
1. Run strategy on actual data to establish a baseline, calculate basic metrics
2. Generate synthetic market paths by applying a Stationary Bootstrapping algorithm 
   (i.e. block length vary randomly accroding to geometeric distribution)
   Replicate this process 5000 times to create 5000 unique, suffled datasets
3. Calculate metrics across all paths
4. Construct the 95% (this number is variable) Percentile Confidence Interval: sort 5000 generated metrics from
   lowest to highest 
   Extract 2.5th - 97.5th percentile 
5. Compare steps 1 to 4:
    - if Sharpe Ratio of 0 (or a benchmark index) falls inside the 95% confidence interval -- reject 
        (statistically indistinguishable from noise)
    - if entire confidence interval > minimum threshold --> statistical significance
'''
import numpy as np
import pandas as pd
from scipy import stats
from monte_carlo import MonteCarlo
from ..core_logic.engine.engine import BacktestEngine


class BootstrappedConfidenceIntervals(MonteCarlo):
    def __init__(self, data, backtest_engine: BacktestEngine,
                 epsilon: float = 0.01, confidence: float = 0.95, k: int = 30,
                 n_bootstrap: int = 5000, metric: str = "sharpe",
                 null_value: float = 0.0, min_threshold: float = None,
                 avg_block_length: int = 20):
        """
        Parameters
        ----------
        n_bootstrap       : number of synthetic paths (default 5000)
        metric            : 'sharpe' | 'cagr' | 'max_drawdown' — scalar to test
        null_value        : benchmark to compare against (default 0.0 for Sharpe of noise)
        min_threshold     : if set, entire CI must exceed this to pass
        avg_block_length  : expected block length L for stationary bootstrap (geometric mean)
        """
        super().__init__(data, backtest_engine, epsilon, confidence, k)
        self.n_bootstrap     = n_bootstrap
        self.metric          = metric
        self.null_value      = null_value
        self.min_threshold   = min_threshold
        self.avg_block_length = avg_block_length

        # populated after run()
        self.baseline_metric  = None
        self.bootstrap_metrics = []
        self.ci               = None          # (lower, upper)
        self.verdict          = None

    # ------------------------------------------------------------------
    # Stationary bootstrap: resample self.data preserving autocorrelation
    # ------------------------------------------------------------------
    def _stationary_bootstrap(self) -> pd.DataFrame:
        """
        Politis & Romano (1994) stationary bootstrap.
        Block lengths are geometrically distributed with mean avg_block_length,
        so p = 1 / avg_block_length.
        Returns a resampled DataFrame of the same length as self.data.
        """
        data = self.data
        n = len(data)
        p = 1.0 / self.avg_block_length
        indices = []

        while len(indices) < n:
            # random starting index
            start = np.random.randint(0, n)
            # geometric block length (at least 1)
            block_len = np.random.geometric(p)
            for j in range(block_len):
                indices.append((start + j) % n)   # wrap around

        indices = indices[:n]
        resampled = data.iloc[indices].reset_index(drop=True)
        return resampled

    # ------------------------------------------------------------------
    # Compute scalar metric from engine history # TODO: use metrics_calculator.py for this
    # ------------------------------------------------------------------
    def _compute_metric(self, history: list) -> float:
        df = pd.DataFrame(history)                         # timestamp, price, portfolio_value, position
        df = df.set_index("timestamp").sort_index()

        pv = df["portfolio_value"]
        daily_returns = pv.pct_change().dropna()

        if self.metric == "sharpe":
            if daily_returns.std() == 0:
                return 0.0
            return (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)

        elif self.metric == "cagr":
            total_return = pv.iloc[-1] / pv.iloc[0]
            n_years = len(pv) / 252
            return total_return ** (1 / n_years) - 1

        elif self.metric == "max_drawdown":
            rolling_max = pv.cummax()
            drawdown = (pv - rolling_max) / rolling_max
            return drawdown.min()                          # negative number

        else:
            raise ValueError(f"Unknown metric: {self.metric!r}")

    # ------------------------------------------------------------------
    # MonteCarlo hook: one bootstrap trial
    # ------------------------------------------------------------------
    def _run_once(self) -> float:
        synthetic_data = self._stationary_bootstrap()
        history = self.engine.run(synthetic_data)          # engine returns self.history list
        return self._compute_metric(history)

    # ------------------------------------------------------------------
    # Full pipeline (overrides base run())
    # ------------------------------------------------------------------
    def run(self) -> dict:
        """
        1. Baseline run on actual data
        2. find_n() to determine sufficient n (uses _run_once → bootstrap paths)
        3. Run remaining (n - k) trials, reusing the k sample trials from find_n
        4. Build CI, compare against null and threshold
        Returns a results dict.
        """
        # Step 1: baseline on real data
        baseline_history = self.engine.run(self.data)
        self.baseline_metric = self._compute_metric(baseline_history)

        # Step 2: find n via sample variance (runs k bootstrap trials internally)
        self.find_n()
        n = max(self.n, self.n_bootstrap)   # respect both the stat requirement and desired 5000

        # Step 3: collect all bootstrap metrics
        #   find_n() already ran k trials — reuse their scalar results
        bootstrap_metrics = list(self.sample_results)   # length k, already scalars

        for _ in range(n - self.k):
            bootstrap_metrics.append(self._run_once())

        self.bootstrap_metrics = bootstrap_metrics

        # Step 4: construct CI
        alpha = 1 - self.confidence
        lower = np.percentile(bootstrap_metrics, 100 * alpha / 2)
        upper = np.percentile(bootstrap_metrics, 100 * (1 - alpha / 2))
        self.ci = (lower, upper)

        # Step 5: verdict
        null_inside_ci   = lower <= self.null_value <= upper
        above_threshold  = (self.min_threshold is None) or (lower > self.min_threshold)

        if null_inside_ci:
            self.verdict = "REJECT — strategy indistinguishable from noise"
        elif not above_threshold:
            self.verdict = f"REJECT — CI does not clear minimum threshold {self.min_threshold}"
        else:
            self.verdict = "PASS — statistically significant"

        return {
            "baseline":         self.baseline_metric,
            "ci_lower":         lower,
            "ci_upper":         upper,
            "n_simulations":    n,
            "null_inside_ci":   null_inside_ci,
            "verdict":          self.verdict,
        }

