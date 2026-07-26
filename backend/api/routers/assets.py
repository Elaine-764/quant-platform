# backend/api/routers/assets.py
from fastapi import APIRouter, Query, Response
from typing import Optional

router = APIRouter()

ASSET_REGISTRY = {
    "equity": ["AAPL", "MSFT", "SPY", "QQQ"],
    "bond": ["TLT", "IEF", "AGG", "SHY"],
}

@router.get("/assets")
def list_assets(response: Response, type: Optional[str] = Query(None, description="equity | bond | any")):
    response.headers["Cache-Control"] = "no-store"
    if type in (None, "any"):
        return {"assets": sorted({t for tickers in ASSET_REGISTRY.values() for t in tickers})}
    return {"assets": ASSET_REGISTRY.get(type, [])}