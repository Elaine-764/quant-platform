import os
import pandas as pd

BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed")
)

EXPECTED_SCHEMAS = {
    "price": ["date", "open", "high", "low", "close", "volume"],
    "^VIX": ["date", "open", "high", "low", "close", "volume"],
    "CPI": ["date", "cpi"],
    "10Y_Treasury": ["date", "yield"],
    "2Y_Treasury": ["date", "yield"],
    "US_Interest_Rate": ["date", "rate"],
    "EUR_Interest_Rate": ["date", "rate"],
    "Corporate_Bond_Yield": ["date", "yield"],
    "EURUSD": ["date", "open", "high", "low", "close", "volume"],
    "GLD": ["date", "open", "high", "low", "close", "volume"],
    "SPY": ["date", "open", "high", "low", "close", "volume"],
    "TLT": ["date", "open", "high", "low", "close", "volume"],
    "QQQ": ["date", "open", "high", "low", "close", "volume"],
    "WTI": ["date", "open", "high", "low", "close", "volume"],
}

def _validate_columns(df, expected_columns, filename):
    missing = [c for c in expected_columns if c not in df.columns]
    if missing:
        raise ValueError(
            f"{filename} is missing required columns: {missing}. "
            f"Found columns: {list(df.columns)}"
        )

def load_processed_csv(filename, expected_columns=None, index_col="date", parse_dates=True):
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Processed file not found: {path}")

    df = pd.read_csv(path, parse_dates=[index_col] if parse_dates and index_col in expected_columns else None)
    if expected_columns is not None:
        _validate_columns(df, expected_columns, filename)

    if index_col in df.columns:
        df = df.set_index(index_col)

    return df

def load_asset_data(symbol):
    filename = f"{symbol}.csv"
    expected = EXPECTED_SCHEMAS.get(symbol, EXPECTED_SCHEMAS["price"])
    return load_processed_csv(filename, expected_columns=expected)

def validate_processed_files():
    errors = []
    for symbol, expected in EXPECTED_SCHEMAS.items():
        filename = f"{symbol}.csv"
        path = os.path.join(BASE_DIR, filename)
        if not os.path.exists(path):
            errors.append(f"Missing file: {filename}")
            continue
        try:
            load_processed_csv(filename, expected_columns=expected)
        except Exception as exc:
            errors.append(str(exc))
    if errors:
        raise RuntimeError("Data validation failed:\n" + "\n".join(errors))

        