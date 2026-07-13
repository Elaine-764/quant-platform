from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from .enhancements import PositionSizer, Enhancements, Filter


class StrategyRequest(BaseModel):
	strategy: str
	instrument: str
	params: Dict[str, Any] = Field(default_factory=dict)
	enhancements: Enhancements
	position_sizer: Optional[PositionSizer] = None


class StrategyResponse(BaseModel):
	strategy: str
	signal_count: int = 0
	notes: Optional[str] = None


# ------------------------
# Specific strategy models
# ------------------------

class EquityBonds(BaseModel):
	equity: str
	bond: str
	lookback: float
	bond_momentum_window: int

class DeltaHedging(BaseModel):
    asset: str
    strike: float
    days_to_expiry: int
    r: float = 0.04
    assumed_vol: float = None
    cash_balance: float = 0.0

class Cointegration(BaseModel):
	asset1: str
	asset2: str
	window: int
	threshold: float
	beta: float

class Oscillator(BaseModel):
    asset: str
    window: int
    buy_threshold: float
    sell_threshold: float
	
class MARequest(BaseModel):
	asset: str
	short_window: int = 20
	long_window: int = 50


class BollingerRequest(BaseModel):
	asset: str
	window: int = 20
	num_std: float = 2.0


class ZScoreRequest(BaseModel):
	asset: str
	window: int = 20
	threshold: float = 2.0


class PairsTradingRequest(BaseModel):
	assets: List[str]
	window: int = 60
	threshold: float = 2.0
	hedge_ratio: Optional[float] = None


class EngleGrangerRequest(PairsTradingRequest):
	pass


class JohansenRequest(PairsTradingRequest):
	confidence_level: int = 95


class MLPRequest(BaseModel):
	asset_names: List[str]
	input_num_metrics: int
	input_num_days: int
	input_num_assets: int
	learning_rate: float = 1e-3
	epochs: int = 100
	device: Optional[str] = None


class RegimeSwitchRequest(BaseModel):
	asset: str
	mean_reversion_strategy: Dict[str, Any]
	momentum_strategy: Dict[str, Any]
	vol_window: int = 20
	vol_threshold: float = 0.015

