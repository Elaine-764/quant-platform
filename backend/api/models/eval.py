from typing import Optional
from pydantic import BaseModel
from api.models.engine import GenericStrategyRequest


class NoiseOHLCRequest(BaseModel):
    strategy: GenericStrategyRequest
    strategy_name: str                  # e.g. "momentum" — passed to REGISTRY.get()
    noise_factor: float = 0.05
    vol_window: int = 20
    metric: str = "sharpe"
    epsilon: float = 0.01
    confidence: float = 0.95
    k: int = 30


class BootstrapRequest(BaseModel):
    strategy: GenericStrategyRequest
    strategy_name: str
    n_bootstrap: int = 5000
    metric: str = "sharpe"
    null_value: float = 0.0
    min_threshold: Optional[float] = None
    avg_block_length: int = 20
    epsilon: float = 0.01
    confidence: float = 0.95
    k: int = 30


class NoiseResponse(BaseModel):
    mean_metric: float
    std_metric: float
    ci_lower: float
    ci_upper: float
    n_simulations: int


class BootstrapResponse(BaseModel):
    baseline: float
    ci_lower: float
    ci_upper: float
    n_simulations: int
    null_inside_ci: bool
    verdict: str