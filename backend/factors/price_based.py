from .base_factor import Factor
import numpy as np
import ta

class PriceBasedFactors(Factor):
    def __init__(self):
        self.close_price = 'Close'

class Returns(PriceBasedFactors):
    def __init__(self, asset, window):
        self.asset = asset
        self.window = window

    def output_column(self):
        return f"{self.asset}_ret_{self.window}"

    def compute(self, data, tt=None):
        out = self.output_column()

        data[out] = data[self.close_price].pct_change(self.window)
        return data
    
class MovingAverage(PriceBasedFactors):
    def __init__(self, asset, window):
        super().__init__()
        self.asset = asset
        self.window = window

    def output_column(self):
        return f"{self.asset}_ma_{self.window}"

    def compute(self, data, t=None):
        out = self.output_column()

        data[out] = data[self.close_price].rolling(self.window).mean()
        return data
    
class BollingerBands(PriceBasedFactors):
    def __init__(self, asset, window, num_std):
        super().__init__()
        self.asset = asset
        self.window = window
        self.num_std = num_std

    def output_column(self):
        return f"{self.asset}_ba_{self.window}"

    def compute(self, data, t=None):
        # 1. Calculate the Middle Band (SMA)
        sma = data[self.close_price].rolling(window=self.window).mean() # TODO: what is close_price?
        
        # 2. Calculate the Rolling Standard Deviation
        # Using ddof=0 for population standard deviation matches tools like TradingView
        std = data[self.close_price].rolling(window=self.window).std(ddof=0)
        
        # 3. Calculate Upper and Lower Bands
        upper_band = sma + (std * self.num_std)
        lower_band = sma - (std * self.num_std)
        
        return sma, upper_band, lower_band
            
    

class SMA(MovingAverage):
    def __init__(self, asset, window):
        super().__init__(asset, window)

    def output_column(self):
        return f"{self.asset}_sma_{self.window}"

class EMA(MovingAverage):
    def __init__(self, asset, window):
        super().__init__(asset, window)

    def output_column(self):
        return f"{self.asset}_ema_{self.window}"

    def compute(self, data, tt=None):
        out = self.output_column()
        data[out] = data[self.close_price].ewm(span=self.window).mean()
        return data

class RSI(PriceBasedFactors):
    def __init__(self, asset, window=14):
        super().__init__()
        self.asset = asset
        self.window = window

    def output_column(self):
        return f"{self.asset}_rsi_{self.window}"

    def compute(self, data, tt=None):
        col = self.close_price
        out = self.output_column()

        delta = data[col].diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(self.window).mean()
        avg_loss = loss.rolling(self.window).mean()

        rs = avg_gain / avg_loss
        data[out] = 100 - (100 / (1 + rs))

        return data

class ADX(PriceBasedFactors):
    def __init__(self, asset, window=14):
        self.asset = asset
        self.window = window

    def output_column(self):
        return f"{self.asset}_adx_{self.window}"

    def compute(self, data, tt=None):
        high = data['High']
        low = data['Low']
        close = data['Close']

        indicator = ta.trend.ADXIndicator(
            high=high,
            low=low,
            close=close,
            window=self.window
        )

        data[self.output_column()] = indicator.adx()
        data[f"{self.asset}_plus_di"] = indicator.adx_pos()
        data[f"{self.asset}_minus_di"] = indicator.adx_neg()

        return data
