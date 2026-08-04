import yfinance as yf
import pandas as pd

tickers = [
    # Broad Market
    "VTI", "SPY", "VOO", "QQQ", "IWM", "VEA", "VWO",
    # Bonds
    "TLT", "IEF", "SHY", "AGG", "LQD", "HYG", "TIP",
    # Sectors
    "XLF", "XLK", "XLE", "XLV", "XLU", "XLP", "XLY", "XLRE",
    # Commodities
    "GLD", "IAU", "SLV", "USO", "PDBC",
    # REITs
    "VNQ", "VNQI",
    # Alternatives
    "VXX", "BITO",
    # Currency
    "UUP",
    # Volatility
    "^VIX",
    # S&P 500
    "^GSPC",
    # Cboe 10-year treasury note yield index
    "^TNX",
]
data = yf.download(tickers, period="10y", interval="1d", auto_adjust=True, group_by="column")

for ticker in tickers:
    df = data.xs(ticker, axis=1, level=1)  # slice out each ticker
    df.to_csv(f"raw/{ticker}.csv")
    print(f"Saved {ticker}.csv")