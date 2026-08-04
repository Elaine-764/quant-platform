import pandas as pd
import numpy as np
from api.strategy_utils import load_prices_df
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"

def sanitize_float(val):
    """Converts numpy types to python floats, converting NaN/inf to None for JSON safety."""
    if pd.isna(val) or np.isinf(val):
        return None
    return float(val)

class MetricsCalculator:
    def __init__(self, history):
        self.history = history
        if not history:
            raise ValueError("History data is empty")

        base_df = pd.DataFrame(history)
        base_df['date'] = pd.to_datetime(base_df['date'])
        base_df.set_index('date', inplace=True)

        # explode the nested price dict → columns like "price.SPY", "price.TLT"
        price_df = pd.json_normalize(history).set_index(
            pd.Index(base_df.index, name="date")
        ).filter(like="price.")
        price_df.columns = price_df.columns.str.removeprefix("price.")

        self._df = base_df.drop(columns=["price"]).join(price_df)
        self.equity_curve = self._df["portfolio_value"]
        self.monthly_equity_curve = self._df.resample("ME").last()
        self.yearly_equity_curve = self._df.resample("YE").last()

        self.start_date = pd.to_datetime(price_df.index.min())
        self.end_date = pd.to_datetime(price_df.index.max())
        self.ret = self.returns()
        
        # Calendar days divided by 365 gives actual elapsed annual timeline
        days_diff = (self.end_date - self.start_date).days
        self.num_years = max(days_diff / 365.25, 1 / 365.25) 
        
        self.total_ret = self.total_return()
        self.annual_ret = self.annual_return()
        self.vol = self.volatility()
        self.vol_annualized = self.vol * np.sqrt(252) # Standard Vol Annualization multiplier


    def all(self):
        returns = self.returns()
        return {
            "final_portfolio_value": sanitize_float(self.final_portfolio_value()),
            "total_return": sanitize_float(self.total_ret),
            "annual_return": sanitize_float(self.annual_ret),
            "sharpe": None if returns.std() == 0 else sanitize_float(self.sharpe()),
            "max_drawdown": sanitize_float(self.max_drawdown()),
            "volatility": sanitize_float(self.vol),
            "annual_volatility": sanitize_float(self.vol_annualized),
            "information_ratio": sanitize_float(self.information_ratio()),
            "sortino_ratio": sanitize_float(self.sortino_ratio()),
            "consistency": self.consistency()
        }

    def final_portfolio_value(self):
        return self.equity_curve.iloc[-1] if not self.equity_curve.empty else 0.0

    def returns(self):
        return self.equity_curve.pct_change().dropna()

    def total_return(self):
        if self.equity_curve.empty or self.equity_curve.iloc[0] == 0:
            return 0.0
        return self.equity_curve.iloc[-1] / self.equity_curve.iloc[0] - 1

    def annual_return(self):
        # Prevent fractional roots of negative numbers
        if self.total_ret <= -1:
            return -1.0
        return (self.total_ret + 1) ** (1 / self.num_years) - 1

    def sharpe(self):
        r = self.returns()
        return (r.mean() / r.std()) * np.sqrt(252) if r.std() != 0 else 0.0

    def information_ratio(self):
        sp_500_return = self.find_sp_500_ret()
        active_return = self.annual_ret - sp_500_return
        
        # Avoid dividing tracking error calculations incorrectly by zero
        if self.vol_annualized == 0 or active_return == 0:
            return 0.0
        
        # Simplified Tracking Error Proxy using strategy tracking variance limits
        return active_return / self.vol_annualized

    def sortino_ratio(self):
        rf_rate = self.find_rf_rate()
        r = self.returns()
        downside_returns = r[r < 0]
        
        if downside_returns.empty or downside_returns.std() == 0:
            return 0.0
            
        downside_vol_annualized = downside_returns.std() * np.sqrt(252)
        return (self.annual_ret - rf_rate) / downside_vol_annualized

    def max_drawdown(self):
        if self.equity_curve.empty:
            return 0.0
        cummax = self.equity_curve.cummax()
        drawdown = (self.equity_curve - cummax) / cummax
        return drawdown.min()

    def volatility(self):
        return self.ret.std() if not self.ret.empty else 0.0

    def consistency(self):
        monthly_returns = self.monthly_equity_curve['portfolio_value'].pct_change().dropna()
        yearly_returns = self.yearly_equity_curve['portfolio_value'].pct_change().dropna()

        pos_months = (monthly_returns > 0).sum() if not monthly_returns.empty else 0
        pos_years = (yearly_returns > 0).sum() if not yearly_returns.empty else 0

        return {
            'pos_month_pct': sanitize_float(pos_months / len(monthly_returns)) if len(monthly_returns) > 0 else 0.0,
            'pos_year_pct': sanitize_float(pos_years / len(yearly_returns)) if len(yearly_returns) > 0 else 0.0,
            'median_monthly_returns': sanitize_float(np.median(monthly_returns)) if not monthly_returns.empty else 0.0,
            'median_yearly_returns': sanitize_float(np.median(yearly_returns)) if not yearly_returns.empty else 0.0,
            'std_monthly_returns': sanitize_float(np.std(monthly_returns)) if not monthly_returns.empty else 0.0,
            'std_yearly_returns': sanitize_float(np.std(yearly_returns)) if not yearly_returns.empty else 0.0
        }

    def find_sp_500_ret(self):
        try:
            data = load_prices_df(DATA_DIR, "^GSPC")
            data['Date'] = pd.to_datetime(data['Date'])
            data = data[(data['Date'] >= self.start_date) & (data['Date'] <= self.end_date)]
            if data.empty or len(data) < 2:
                return 0.0
            sp_rate = data['Close'].iloc[-1] / data['Close'].iloc[0] - 1
            return (sp_rate + 1) ** (1 / self.num_years) - 1
        except Exception:
            return 0.0
    
    def find_rf_rate(self):
        try:
            data = load_prices_df(DATA_DIR, "^TNX")
            data['Date'] = pd.to_datetime(data['Date'])
            data = data[(data['Date'] >= self.start_date) & (data['Date'] <= self.end_date)]
            if data.empty:
                return 0.0
            # ^TNX holds yield percentages multiplied by 10 (e.g. 45.0 = 4.5%). Divide by 1000 for decimal rate.
            latest_yield = data['Close'].iloc[-1] / 100.0
            return latest_yield
        except Exception:
            return 0.0
