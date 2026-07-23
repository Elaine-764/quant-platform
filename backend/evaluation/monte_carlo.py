'''
Monte Carlo base class for Noise Injection and Bootstrapped Confidence Intervals
'''
import math
from scipy import stats
from core_logic.engine.engine import BacktestEngine


class MonteCarlo():
    def __init__(self, data, backtest_engine: BacktestEngine, epsilon: float = 0.01,
                 confidence: float = 0.95, k: int = 30):
        """
        Parameters
        ----------
        data             : market data passed to each simulation
        backtest_engine  : BacktestEngine instance whose .run() returns a scalar metric
        epsilon          : acceptable absolute error |μ - m| < ε
        confidence       : desired confidence level (e.g. 0.95 for 95%)
        k                : number of sample simulations used to estimate variance
        """
        self.data = data
        self.engine = backtest_engine
        self.epsilon = epsilon
        self.confidence = confidence
        self.k = k

        self.n = None          # determined by find_n()
        self.sample_mean = None
        self.sample_results = []

    # ------------------------------------------------------------------
    # Internal: one simulation trial → scalar metric
    # ------------------------------------------------------------------
    def _run_once(self) -> float:
        """
        Override in subclasses to inject noise / resample before calling
        the engine, then return a single scalar performance metric.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Step 1: determine sufficiently large n
    # ------------------------------------------------------------------
    def find_n(self) -> int:
        """
        Runs k sample simulations, computes the sample variance s² with
        the numerically-stable one-pass algorithm, then returns

            n = ceil( s² · z² / ε² )

        Also caches the k sample results and their running mean so that
        run() can reuse them instead of discarding the work.
        """
        k = self.k
        z = stats.norm.ppf(1 - (1 - self.confidence) / 2)   # two-tailed z

        # ---- one-pass Welford variance (matches pseudocode exactly) ----
        S = 0.0          # accumulator (called s in the pseudocode, S here to avoid shadowing)
        m_prev = None    # m_{i-1}
        results = []

        for i in range(1, k + 1):
            r = self._run_once()
            results.append(r)

            if i == 1:
                m_cur = r               # m_1 = r_1
                # S stays 0
            else:
                delta   = r - m_prev                    # δ_i = r_i - m_{i-1}
                m_cur   = m_prev + delta / i            # m_i = m_{i-1} + δ_i / i
                S       = S + ((i - 1) / i) * delta**2 # S_i = S_{i-1} + ((i-1)/i)·δ_i²

            m_prev = m_cur

        s2 = S / (k - 1)               # sample variance

        self.sample_results = results
        self.sample_mean    = m_cur     # m_k: mean of the k sample runs

        n = math.ceil(s2 * z**2 / self.epsilon**2)
        self.n = n
        return n

    # ------------------------------------------------------------------
    # Step 2: run the full simulation
    # ------------------------------------------------------------------
    def run(self) -> float:
        """
        Calls find_n() to determine n, then:
          - if n ≤ k  →  m_k is already within ε of μ; return it directly
          - if n > k  →  run (n - k) additional trials and fold them in
        Returns the grand mean m over all n simulations.
        """
        if self.n is None:
            self.find_n()

        n = self.n
        k = self.k

        if n <= k:
            # The k sample runs are already sufficient
            self.final_mean = self.sample_mean
            return self.final_mean

        # Fold k sample results into running sum, then continue to n
        running_sum = self.sample_mean * k   # s = m_k * k

        for _ in range(n - k):
            running_sum += self._run_once()

        self.final_mean = running_sum / n
        return self.final_mean