import pandas as pd

class MetricsCalculator:
    def __init__(self, history):
        self.history = history
        self.equity_curve = [h["portfolio_value"] for h in history]
    
    def all(self):
        return {
            "portfolio_value": self.final_portfolio_value,
            "total_return": self.returns,
            # and so on
        }

    def final_portfolio_value(self):
        return self.equity_curve[-1]

    def returns(self):
        return self.equity_curve.pct_change()
    
    def annual_return(self):
        raise NotImplementedError

    def sharpe(self):
        r = self.returns()
        return r.mean() / r.std()
    def information_ratio(self):
        raise NotImplementedError
    
    def sortino_ratio(self):
        raise NotImplementedError

    def drawdowns(self):
        cummax = self.equity_curve.cummax()
        drawdown = (self.equity_curve - cummax) / cummax
        return {
            'max': drawdown.min(),
            'avg': drawdown.mean(),
            'median': drawdown.median(),
            'avg_duration': NotImplementedError
        }
   
    def volatility(self):
        return self.equity_curve.std()
    
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