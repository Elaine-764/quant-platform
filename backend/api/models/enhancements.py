from typing import Dict, Any, Optional, Union, List
from pydantic import BaseModel, Field

class Enhancements(BaseModel):
    filters: Optional[List["Filter"]]
    position_sizers: Optional[List["PositionSizer"]]

# class EnhancementConfig(BaseModel):
#     name: str
#     params: Dict[str, Any] = Field(default_factory=dict)

class Filter(BaseModel):
    name: str
    filter: Union["VolFilter", "MomentumFilter", "VolumeFilter", "VolumeFilter", "MaxDrawdownControl", "MaxPositionSize",
                  "ConsecutiveLossControl"]

class VolFilter(Filter):
    min_vol: float
    max_vol: float
    lookback: int

class MomentumFilter(Filter):
    lookback: int

class VolumeFilter(Filter):
    lookback: int
    min_volume_ratio: float

class StopLoss(Filter):
    stop_loss_pct: float

class MaxDrawdownControl(Filter):
    max_dd_pct: float

class MaxPositionSize(Filter):
    max_pos_pct: float

class ConsecutiveLossControl(Filter):
    max_consec_losses: float

Filter.model_rebuild()


class PositionSizer(BaseModel):
    name: str
    sizer: Union["FractionalSizer", "VolatilityScaling", "KellyCriterion", "DynamicKelly"]


class FractionalSizer(PositionSizer):
    fraction: float = 0.25


class VolatilityScaling(PositionSizer):
    lookback: int = 20
    target_volatility: float = 0.015


class KellyCriterion(PositionSizer):
    win_rate: float = 0.55
    avg_win: float = 0.02
    avg_loss: float = 0.01
    kelly_fraction: float = 0.25


class DynamicKelly(PositionSizer):
    lookback_trades: int = 20
    kelly_fraction: float = 0.25


PositionSizer.model_rebuild()
Enhancements.model_rebuild()

        