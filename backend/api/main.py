from fastapi import FastAPI, HTTPException
from pathlib import Path
import os

from api.models.engine import HealthResponse, InstrumentListResponse, PricesResponse
from api.strategy_utils import load_prices
from api.routers import strategies, backtest, engine, assets

app = FastAPI(title="Quant Platform API")

app.include_router(strategies.router)
app.include_router(backtest.router)
app.include_router(engine.router)
app.include_router(assets.router) 

# data directory (processed CSVs)
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"


@app.get("/")
async def root():
    return {"message": "Quant platform backend running."}


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse()


@app.get("/instruments", response_model=InstrumentListResponse)
def list_instruments():
    if not DATA_DIR.exists():
        raise HTTPException(status_code=500, detail=f"Data folder not found: {DATA_DIR}")
    files = [f.name for f in DATA_DIR.iterdir() if f.is_file() and f.suffix.lower() == ".csv"]
    symbols = [os.path.splitext(f)[0] for f in files]
    return InstrumentListResponse(instruments=symbols)


@app.get("/instruments/{symbol}/prices", response_model=PricesResponse)
def get_prices(symbol: str):
    try:
        data = load_prices(DATA_DIR, symbol)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return PricesResponse(symbol=symbol, data=data)