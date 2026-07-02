import numpy as np

class RiskAnalyzer:
    def var(self, returns, alpha=0.05):
        return np.percentile(returns, alpha * 100)