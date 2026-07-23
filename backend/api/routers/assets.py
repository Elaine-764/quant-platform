# assets_router.py
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()

# TODO: replace with a real source (DB table, config file, or a directory scan
# of your price-data folder). Keeping it as a simple in-memory registry for now.
ASSET_REGISTRY = {
    "equity": ["AAPL", "MSFT", "SPY", "QQQ"],
    "bond": ["TLT", "IEF", "AGG", "SHY"],
}

@router.get("/assets")
def list_assets(type: Optional[str] = Query(None, description="equity | bond | any")):
    if type in (None, "any"):
        return {"assets": sorted({t for tickers in ASSET_REGISTRY.values() for t in tickers})}
    return {"assets": ASSET_REGISTRY.get(type, [])}