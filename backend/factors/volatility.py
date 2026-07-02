from .base_factor import Factor

class VolatilityFactor(Factor):
    def __init__(self, window=10):
        self.window = window

    def compute(self, data, t):
        returns = data["returns"][t-self.window:t]
        return returns.std()
    

class ATR(Factor):
    def __init__(self, window=14):
        self.window = window

    def compute(self, data, t):
        if t < self.window:
            return None
        high = data['high'][t-self.window:t]
        low = data['low'][t-self.window:t]
        close = data['close'][t-self.window:t]
        
        tr = []
        for i in range(1, len(high)):
            tr1 = high.iloc[i] - low.iloc[i]
            tr2 = abs(high.iloc[i] - close.iloc[i-1])
            tr3 = abs(low.iloc[i] - close.iloc[i-1])
            tr.append(max(tr1, tr2, tr3))
        
        if tr:
            atr = sum(tr) / len(tr)
        else:
            atr = 0
        return atr

class VIX(Factor):
    def __init__(self):
        import pandas as pd
        self.vix_df = pd.read_csv('data/processed/^VIX.csv')

    def compute(self, data, t):
        # Assuming the CSV has a 'close' column and is indexed by time t
        return self.vix_df.iloc[t]['close']
