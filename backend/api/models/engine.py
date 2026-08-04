from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from api.models.enhancements import EnhancementsModel

class BacktestRequest(BaseModel):
    strategy: str
    instrument: str
    start_cash: float = 100000.0
    params: Dict[str, Any] = Field(default_factory=dict)
    enhancements: List[EnhancementsModel] = Field(default_factory=list)

class BacktestResult(BaseModel):
    history: List[Dict[str, Any]]
    metrics: Optional[Dict[str, Any]] = None

class InstrumentListResponse(BaseModel):
    instruments: List[str]


class PricesResponse(BaseModel):
    symbol: str
    # preserve CSV-style capitalization for returned price rows (e.g. 'Date', 'Close')
    data: List[Dict[str, Any]]


class MetricsRequest(BaseModel):
    strategy: str
    signal_count: int
    notes: Any
    history: List[Dict[str, Any]]

class MetricsResponse(BaseModel):
    final_portfolio_value: float
    total_return: float
    annual_return: float
    sharpe: Optional[float] = None
    max_drawdown: Optional[float] = None
    volatility: Optional[float] = None
    annual_volatility: float
    information_ratio: float
    sortino_ratio: float
    consistency: Dict[str, Any]

class HealthResponse(BaseModel):
    status: str = "ok"

class TransactionCosts(BaseModel):
    fixed: float
    pct: float
    slippage_pct: float
    by_asset: Optional[Dict[str, Any]] = None

class PortfolioModel(BaseModel):
    initial_cash: float
    transaction_costs: TransactionCosts


class GenericStrategyRequest(BaseModel):
    params: Dict[str, Any]
    enhancements: EnhancementsModel
    portfolio: PortfolioModel


