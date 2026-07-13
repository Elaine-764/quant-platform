from typing import Optional
from pydantic import BaseModel


class BootstrapRequest(BaseModel):
    strategy: str
    instrument: str
    start_cash: float = 100000.0
    n_bootstrap: int = 5000
    metric: str = "sharpe"
    confidence: float = 0.95
    k: int = 30
    null_value: float = 0.0
    min_threshold: Optional[float] = None
    avg_block_length: int = 20
    epsilon: float = 0.01

class BootstrapRequest(BaseModel):
    strategy: str
    instrument: str
    start_cash: float = 100000.0
    # monte carlo params
    n_bootstrap: int = 5000
    metric: str = "sharpe"
    confidence: float = 0.95
    k: int = 30
    null_value: float = 0.0
    min_threshold: Optional[float] = None
    avg_block_length: int = 20
    epsilon: float = 0.01


class BootstrapResponse(BaseModel):
    baseline: float
    ci_lower: float
    ci_upper: float
    n_simulations: int
    null_inside_ci: bool
    verdict: str


class NoiseOHLCRequest(BaseModel):
    strategy: str
    instrument: str
    start_cash: float = 100000.0
    noise_factor: float = 0.05
    vol_window: int = 20
    metric: str = "sharpe"
    epsilon: float = 0.01
    confidence: float = 0.95
    k: int = 30


class NoiseResponse(BaseModel):
    mean_metric: float
    std_metric: float
    ci_lower: float
    ci_upper: float
    n_simulations: int
