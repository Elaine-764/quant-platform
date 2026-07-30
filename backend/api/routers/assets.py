# backend/api/routers/assets.py
from fastapi import APIRouter, Query, Response
from typing import Optional

router = APIRouter()

ASSET_REGISTRY = {
    "equity": {
        "VTI": "Total U.S. stock market",
        "SPY": "S&P 500",
        "VOO": "S&P 500",
        "QQQ": "Nasdaq-100",
        "IWM": "Russell 2000",
        "VEA": "Developed international equities",
        "VWO": "Emerging markets equities",
        "XLF": "Financial sector equities",
        "XLK": "Technology sector equities",
        "XLE": "Energy sector equities",
        "XLV": "Health care sector equities",
        "XLU": "Utilities sector equities",
        "XLP": "Consumer staples equities",
        "XLY": "Consumer discretionary equities",
        "XLRE": "Real estate equities",
        "VNQ": "U.S. REIT equities",
        "VNQI": "International REIT equities",
    },
    "bond": {
        "TLT": "Long-term U.S. Treasury bonds",
        "IEF": "Intermediate-term U.S. Treasury bonds",
        "SHY": "Short-term U.S. Treasury bonds",
        "AGG": "U.S. aggregate bond market",
        "LQD": "Investment-grade corporate bonds",
        "HYG": "High-yield corporate bonds",
        "TIP": "Treasury Inflation-Protected Securities",
    },
}

def _format(ticker: str, desc: str) -> str:
    return f"{ticker} - {desc}"

@router.get("/assets")
def list_assets(response: Response, type: Optional[str] = Query(None, description="equity | bond | any")):
    response.headers["Cache-Control"] = "no-store"
    if type in (None, "any"):
        all_items = {
            _format(t, d)
            for group in ASSET_REGISTRY.values()
            for t, d in group.items()
        }
        return {"assets": sorted(all_items)}
    group = ASSET_REGISTRY.get(type, {})
    return {"assets": [_format(t, d) for t, d in group.items()]}