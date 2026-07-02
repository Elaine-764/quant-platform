from .base_factor import Factor

class SPY_GLD_Correlation(Factor):
    def __init__(self, window=30):
        self.window = window

    def compute(self, data, t):
        if t < self.window:
            return None
        spy_returns = data['SPY']['returns'][t-self.window:t]
        gld_returns = data['GLD']['returns'][t-self.window:t]
        corr = spy_returns.corr(gld_returns)
        return corr

    def output_column(self, t):
        return f"SPY_GLD_corr_{self.window}"

class EURUSD_SPY_Correlation(Factor):
    def __init__(self, window=30):
        self.window = window

    def compute(self, data, t):
        if t < self.window:
            return None
        eurusd_returns = data['EURUSD']['returns'][t-self.window:t]
        spy_returns = data['SPY']['returns'][t-self.window:t]
        corr = eurusd_returns.corr(spy_returns)
        return corr

    def output_column(self, t):
        return f"EURUSD_SPY_corr_{self.window}"

class Oil_SPY_Correlation(Factor):
    def __init__(self, window=30):
        self.window = window

    def compute(self, data, t):
        if t < self.window:
            return None
        oil_returns = data['WTI']['returns'][t-self.window:t]  # Assuming WTI for oil
        spy_returns = data['SPY']['returns'][t-self.window:t]
        corr = oil_returns.corr(spy_returns)
        return corr

    def output_column(self, t):
        return f"Oil_SPY_corr_{self.window}"

class Treasury_Yield_Spread(Factor):
    def __init__(self):
        import pandas as pd
        self.ten_year = pd.read_csv('data/processed/10Y_Treasury.csv')
        self.two_year = pd.read_csv('data/processed/2Y_Treasury.csv')

    def compute(self, data, t):
        ten_y = self.ten_year.iloc[t]['yield']  # Assuming 'yield' column
        two_y = self.two_year.iloc[t]['yield']
        return ten_y - two_y

    def output_column(self, t):
        return "10Y_2Y_Spread"

class Corporate_Bond_Spread(Factor):
    def __init__(self):
        import pandas as pd
        self.corp_bond = pd.read_csv('data/processed/Corporate_Bond_Yield.csv')
        self.treasury = pd.read_csv('data/processed/10Y_Treasury.csv')

    def compute(self, data, t):
        corp_y = self.corp_bond.iloc[t]['yield']
        treas_y = self.treasury.iloc[t]['yield']
        return corp_y - treas_y

    def output_column(self, t):
        return "Corporate_Bond_Spread"

class Asset_Beta(Factor):
    def __init__(self, asset, window=30):
        self.asset = asset
        self.window = window

    def compute(self, data, t):
        if t < self.window:
            return None
        asset_returns = data[self.asset]['returns'][t-self.window:t]
        market_returns = data['SPY']['returns'][t-self.window:t]
        cov = asset_returns.cov(market_returns)
        var = market_returns.var()
        beta = cov / var if var != 0 else 0
        return beta

    def output_column(self, t):
        return f"{self.asset}_beta_{self.window}"

class VIX_Realized_Vol_Ratio(Factor):
    def __init__(self, window=30):
        import pandas as pd
        self.vix_df = pd.read_csv('data/processed/^VIX.csv')
        self.window = window

    def compute(self, data, t):
        if t < self.window:
            return None
        vix = self.vix_df.iloc[t]['close']
        realized_vol = data['SPY']['returns'][t-self.window:t].std() * (252 ** 0.5)  # Annualized
        return vix / realized_vol if realized_vol != 0 else 0

    def output_column(self, t):
        return f"VIX_Realized_Vol_Ratio_{self.window}"

class CPI_Inflation(Factor):
    def __init__(self):
        import pandas as pd
        self.cpi_df = pd.read_csv('data/processed/CPI.csv')

    def compute(self, data, t):
        if t < 1:
            return None
        current = self.cpi_df.iloc[t]['cpi']
        previous = self.cpi_df.iloc[t-1]['cpi']
        return (current - previous) / previous * 100  # YoY approximation

    def output_column(self, t):
        return "CPI_Inflation"

class Interest_Rate_Differential(Factor):
    def __init__(self):
        import pandas as pd
        self.us_rate = pd.read_csv('data/processed/US_Interest_Rate.csv')
        self.eur_rate = pd.read_csv('data/processed/EUR_Interest_Rate.csv')

    def compute(self, data, t):
        us_r = self.us_rate.iloc[t]['rate']
        eur_r = self.eur_rate.iloc[t]['rate']
        return us_r - eur_r

    def output_column(self, t):
        return "US_EUR_Interest_Diff"

class SPY_QQQ_Spread(Factor):
    def __init__(self, window=30):
        self.window = window

    def compute(self, data, t):
        if t < self.window:
            return None
        spy_prices = data['SPY']['close'][t-self.window:t]
        qqq_prices = data['QQQ']['close'][t-self.window:t]
        spread = (spy_prices - qqq_prices).mean() / spy_prices.mean()  # Normalized spread
        return spread

    def output_column(self, t):
        return f"SPY_QQQ_Spread_{self.window}"
