from .base_factor import Factor

class VolumeSpike(Factor):
    def __init__(self, window=10):
        self.window = window

    def compute(self, data, t):
        if t < self.window:
            return None
        current_vol = data['volume'][t]
        avg_vol = data['volume'][t-self.window:t].mean()
        spike = (current_vol - avg_vol) / avg_vol if avg_vol != 0 else 0
        return spike

    def output_column(self, t):
        return f"volume_spike_{self.window}"

class VolumeMovingAverage(Factor):
    def __init__(self, window=10):
        self.window = window

    def compute(self, data, t):
        if t < self.window:
            return None
        avg_vol = data['volume'][t-self.window:t].mean()
        return avg_vol

    def output_column(self, t):
        return f"volume_ma_{self.window}"

class PriceVolumeDivergence(Factor):
    def __init__(self, window=10):
        self.window = window

    def compute(self, data, t):
        if t < self.window:
            return None
        prices = data['close'][t-self.window:t]
        volumes = data['volume'][t-self.window:t]
        corr = prices.corr(volumes)
        return corr

    def output_column(self, t):
        return f"price_volume_divergence_{self.window}"