import pandas as pd
import numpy as np


class MetricsCalculator:
    def __init__(self, history):
        self.history = history
        # convert to pandas Series for numeric ops
        self._df = pd.DataFrame(history).set_index("timestamp").sort_index()
        self.equity_curve = self._df["portfolio_value"]

    def all(self):
        returns = self.returns()
        return {
            "final_portfolio_value": float(self.final_portfolio_value()),
            "total_return": float(self.total_return()),
            "sharpe": None if returns.std() == 0 else float(self.sharpe()),
            "max_drawdown": float(self.max_drawdown()),
            "volatility": float(self.volatility()),
        }

    def final_portfolio_value(self):
        return self.equity_curve.iloc[-1]

    def returns(self):
        return self.equity_curve.pct_change().dropna()

    def total_return(self):
        return self.equity_curve.iloc[-1] / self.equity_curve.iloc[0] - 1

    def annual_return(self):
        n_years = len(self.equity_curve) / 252
        return (self.equity_curve.iloc[-1] / self.equity_curve.iloc[0]) ** (1 / n_years) - 1

    def sharpe(self):
        r = self.returns()
        return (r.mean() / r.std()) * np.sqrt(252) if r.std() != 0 else 0.0

    def information_ratio(self):
        raise NotImplementedError

    def sortino_ratio(self):
        raise NotImplementedError

    def max_drawdown(self):
        cummax = self.equity_curve.cummax()
        drawdown = (self.equity_curve - cummax) / cummax
        return drawdown.min()

    def drawdowns(self):
        cummax = self.equity_curve.cummax()
        drawdown = (self.equity_curve - cummax) / cummax
        return {
            'max': drawdown.min(),
            'avg': drawdown.mean(),
            'median': drawdown.median(),
            'avg_duration': None
        }

    def volatility(self):
        return self.returns().std() * np.sqrt(252)

    def alpha(self):
        pass

    def beta(self):
        pass

    def consistency(self):
        return {
            'pos_month_pct': None,
            'pos_year_pct': None,
            'median_monthly_returns': None,
            'median_yearly_returns': None,
            'std_monthly_returns': None,
            'std_yearly_returns': None
        }