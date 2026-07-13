# Trading Strategies Research Platform

This quant platform is a research and backtesting workspace for systematic trading strategies. The project is split into a software layer that handles data, execution, evaluation, and APIs, and a strategy layer that focuses on signals, factors, and the math behind the decisions.

## What It Does

- Loads and cleans market data from CSV files under `backend/data/processed/`.
- Runs backtests through a core engine and portfolio model.
- Exposes FastAPI endpoints for backtests, metrics, and Monte Carlo evaluation.
- Organizes reusable factors and strategies so ideas can be tested consistently.

## Project Layout

- `backend/core_logic/` - event loop, engine, and portfolio accounting.
- `backend/strategies/` - strategy definitions and enhancement logic.
- `backend/factors/` - reusable signal features such as momentum, volatility, volume, and cross-asset factors.
- `backend/evaluation/` - metrics, bootstrap confidence intervals, noise injection, walk-forward analysis, and risk tools.
- `backend/data/` - raw and processed market data.
- `backend/api/` - FastAPI app and request/response models.
- `frontend/` - Vite-based frontend for visualization and interaction.

## Strategy and Math Focus

The repository is designed around the idea that a strategy should be built from explicit, testable signal logic.

- Factors should operate on entire DataFrames and create feature columns once before the backtest.
- Strategies consume those factors to produce signals such as trend-following, mean reversion, or regime-based decisions.
- Enhancements can modify the raw signal using filters, position sizing, and risk controls.
- Evaluation uses statistics and simulation to judge whether performance is robust or just noise.

Examples of the mathematical ideas in the repo include:

- Momentum and moving averages.
- RSI, ADX, ATR, and volatility-based features.
- Z-score mean reversion and OU-style half-life ideas.
- Cointegration and pairs trading.
- Regime switching using volatility and cross-asset context.
- Monte Carlo methods such as bootstrapped confidence intervals and noise injection.

## API

The FastAPI app lives in `backend/api/main.py` and currently includes endpoints for:

- Health checks.
- Listing available instruments.
- Returning OHLC price data.
- Running a backtest.
- Computing performance metrics.
- Running bootstrap and noise-based Monte Carlo evaluation.

## Backend Setup

From the repository root:

```bash
python -m uvicorn backend.api.main:app --reload
```

Then open:

```bash
http://127.0.0.1:8000/docs
```

If dependencies are missing, install the backend packages first:

```bash
pip install fastapi uvicorn pandas numpy scipy
```

## Data Format

Processed CSV files are stored in `backend/data/processed/`. The expected columns are the usual OHLCV fields, with `Close` capitalized in the source data. Internally, the backend can normalize those columns when needed for evaluation.

## Notes

- The codebase is still evolving, so some engine and strategy adapters are intentionally lightweight.
- The main design goal is clarity: make signals explicit, keep the math visible, and keep evaluation separate from strategy logic.
- If you add a new strategy, define the required factors first, then wire it into the engine and API.

