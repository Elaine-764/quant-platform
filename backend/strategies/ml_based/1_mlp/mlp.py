import numpy as np
import pandas as pd
import torch
from torch import nn
import torch.optim as optim
from ...base_strategy import Strategy


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def compute_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window).mean()
    avg_loss = loss.rolling(window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)  # neutral value while window is warming up


def compute_macd(close: pd.Series, fast=12, slow=26, signal=9) -> pd.Series:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line  # histogram


def build_features(price_df: pd.DataFrame, macro_df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    price_df: one 'Close' column per tradeable asset, e.g. columns = ['AAPL', 'MSFT', ...]
    macro_df: representative market series, e.g. columns = ['VIX', 'TLT', 'GLD', 'QQQ']
    """
    per_asset_frames = []
    for asset in price_df.columns:
        close = price_df[asset]
        per_asset_frames.append(pd.DataFrame({
            f'{asset}_rsi':   compute_rsi(close),
            f'{asset}_macd':  compute_macd(close),
            f'{asset}_ret20': close.pct_change(window),
            f'{asset}_vol20': close.pct_change().rolling(window).std(),
        }))

    macro_features = pd.DataFrame({'vix_level': macro_df['VIX']})
    for col in ['TLT', 'GLD', 'QQQ']:
        macro_features[f'{col.lower()}_ret'] = macro_df[col].pct_change(window)

    return pd.concat(per_asset_frames + [macro_features], axis=1).dropna()


def build_targets(price_df: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    """Forward `horizon`-day returns per asset — this is what the net predicts."""
    return price_df.shift(-horizon) / price_df - 1


def make_windows(features: pd.DataFrame, targets: pd.DataFrame, num_days: int):
    """
    Slides a `num_days`-length window over the features and flattens it into
    one training row per timestep, aligned with the forward-return target.
    """
    X, Y = [], []
    values = features.values
    for t in range(num_days, len(features)):
        date = features.index[t]
        if date not in targets.index or targets.loc[date].isna().any():
            continue
        X.append(values[t - num_days:t].flatten())
        Y.append(targets.loc[date].values)
    return np.asarray(X, dtype=np.float32), np.asarray(Y, dtype=np.float32)


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

class ReturnPredictorNet(nn.Module):
    def __init__(self, input_size, num_assets, hidden_sizes=(256, 128, 64), dropout=0.2):
        super().__init__()
        layers = []
        prev = input_size
        for h in hidden_sizes:
            layers += [nn.Linear(prev, h), nn.BatchNorm1d(h), nn.ReLU(), nn.Dropout(dropout)]
            prev = h
        layers.append(nn.Linear(prev, num_assets))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


# ---------------------------------------------------------------------------
# Strategy wrapper
# ---------------------------------------------------------------------------

class MLP(Strategy):
    def __init__(self, data_dfs, asset_names, input_num_metrics, input_num_days,
                 input_num_assets, learning_rate=1e-3, epochs=100, device=None):
        super().__init__(None)
        self.data_dfs = data_dfs
        self.asset_names = asset_names
        self.lr = learning_rate
        self.epochs = epochs
        self.input_num_days = input_num_days
        self.input_num_metrics = input_num_metrics
        self.input_num_assets = input_num_assets
        self.input_size = input_num_assets * input_num_days * input_num_metrics

        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.net = ReturnPredictorNet(self.input_size, input_num_assets).to(self.device)
        self.loss_fn = nn.MSELoss()
        self.optimizer = optim.Adam(self.net.parameters(), lr=self.lr)

        self.feature_mean = None
        self.feature_std = None

    def _scale(self, X, fit=False):
        if fit:
            self.feature_mean = X.mean(axis=0, keepdims=True)
            self.feature_std = X.std(axis=0, keepdims=True) + 1e-8
        return (X - self.feature_mean) / self.feature_std

    def fit(self, X, Y, val_frac=0.2, batch_size=64):
        """Trains the net. X, Y come from make_windows(). Splits chronologically
        (most recent val_frac held out at the end) to avoid lookahead leakage."""
        n_val = int(len(X) * val_frac)
        X_train, X_val = X[:-n_val], X[-n_val:]
        Y_train, Y_val = Y[:-n_val], Y[-n_val:]

        X_train = self._scale(X_train, fit=True)
        X_val = self._scale(X_val, fit=False)

        X_train_t = torch.tensor(X_train, device=self.device)
        Y_train_t = torch.tensor(Y_train, device=self.device)
        X_val_t = torch.tensor(X_val, device=self.device)
        Y_val_t = torch.tensor(Y_val, device=self.device)

        loader = torch.utils.data.DataLoader(
            torch.utils.data.TensorDataset(X_train_t, Y_train_t),
            batch_size=batch_size, shuffle=True,
        )

        for epoch in range(self.epochs):
            self.net.train()
            running_loss = 0.0
            for xb, yb in loader:
                self.optimizer.zero_grad()
                loss = self.loss_fn(self.net(xb), yb)
                loss.backward()
                self.optimizer.step()
                running_loss += loss.item() * xb.size(0)
            train_loss = running_loss / len(X_train_t)

            self.net.eval()
            with torch.no_grad():
                val_loss = self.loss_fn(self.net(X_val_t), Y_val_t).item()

            print(f"Epoch {epoch + 1}/{self.epochs} | train_loss: {train_loss:.6f} | val_loss: {val_loss:.6f}")

    def predict(self, X):
        self.net.eval()
        X_scaled = self._scale(X, fit=False)
        X_t = torch.tensor(X_scaled, device=self.device)
        with torch.no_grad():
            return self.net(X_t).cpu().numpy()

    def compute_factors(self):
        raise NotImplementedError(
            "Feature/target/window construction happens offline via "
            "build_features / build_targets / make_windows, then fit(). "
            "This isn't a per-bar factor computation like the other strategies."
        )

    def on_event(self, event):
        raise NotImplementedError(
            "Wire this up once you decide how live windows get assembled "
            "bar-by-bar; predict() gives you the raw model call once you have X."
        )