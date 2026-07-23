# router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError
from typing import Dict, Any
from pathlib import Path


from api.models.enhancements import EnhancementsModel
from api.models.engine import PortfolioModel
from api.models.strategies import StrategyResponse
from api.strategy_utils import load_prices_df, build_portfolio, build_enhancements
from core_logic.engine.engine import BacktestEngine
from api.routers.strategy_registry import REGISTRY
import api.routers.strategy_defs  # noqa: F401  -- ensures registrations run

router = APIRouter()
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

class GenericStrategyRequest(BaseModel):
    params: Dict[str, Any]
    enhancements: EnhancementsModel
    portfolio: PortfolioModel

@router.post("/strategy/{strategy_name:path}", response_model=StrategyResponse, tags=["strategies"])
def run_strategy(strategy_name: str, request: GenericStrategyRequest):
    spec = REGISTRY.get(strategy_name)
    if spec is None:
        raise HTTPException(404, f"Unknown strategy '{strategy_name}'. Available: {sorted(REGISTRY)}")

    try:
        parsed = spec.model(**request.params)
    except ValidationError as e:
        raise HTTPException(422, e.errors())

    tickers = {getattr(parsed, f) for f in spec.asset_fields}
    for f in spec.multi_asset_fields:
        tickers.update(getattr(parsed, f))
    price_data = {t: load_prices_df(DATA_DIR, t) for t in tickers}

    enhcmts = build_enhancements(enhancements=request.enhancements)
    strat = spec.factory(parsed, price_data, enhcmts)
    port = build_portfolio(portfolio=request.portfolio)

    engine = BacktestEngine(data=strat.data, strategy=strat, portfolio=port)
    return engine.run()

@router.get("/strategy", tags=["strategies"])
def list_strategies():
    return {name: spec.model.schema() for name, spec in REGISTRY.items()}