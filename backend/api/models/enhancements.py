from typing import Literal, Union, Optional, List
from typing_extensions import Annotated
from pydantic import BaseModel, Field

class FilterBase(BaseModel):
    name: str


class VolFilter(FilterBase):
    type: Literal["vol_filter"] = "vol_filter"
    min_vol: float
    max_vol: float
    lookback: int

class MomentumFilter(FilterBase):
    type: Literal["momentum_filter"] = "momentum_filter"
    lookback: int

class VolumeFilter(FilterBase):
    type: Literal["volume_filter"] = "volume_filter"
    lookback: int
    min_volume_ratio: float

class StopLoss(FilterBase):
    type: Literal["stop_loss"] = "stop_loss"
    stop_loss_pct: float

class MaxDrawdownControl(FilterBase):
    type: Literal["max_drawdown_control"] = "max_drawdown_control"
    max_dd_pct: float

class MaxPositionSize(FilterBase):
    type: Literal["max_position_size"] = "max_position_size"
    max_pos_pct: float

class ConsecutiveLossControl(FilterBase):
    type: Literal["consecutive_loss_control"] = "consecutive_loss_control"
    max_consec_losses: float

FilterUnion = Annotated[
    Union[VolFilter, MomentumFilter, VolumeFilter, StopLoss, MaxDrawdownControl, MaxPositionSize, ConsecutiveLossControl],
    Field(discriminator="type"),
]


class PositionSizerBase(BaseModel):
    name: str

class FractionalSizer(PositionSizerBase):
    type: Literal["fractional"] = "fractional"
    fraction: float = 0.25

class VolatilityScaling(PositionSizerBase):
    type: Literal["volatility_scaling"] = "volatility_scaling"
    lookback: int = 20
    target_volatility: float = 0.015

class KellyCriterion(PositionSizerBase):
    type: Literal["kelly_criterion"] = "kelly_criterion"
    win_rate: float = 0.55
    avg_win: float = 0.02
    avg_loss: float = 0.01
    kelly_fraction: float = 0.25

class DynamicKelly(PositionSizerBase):
    type: Literal["dynamic_kelly"] = "dynamic_kelly"
    lookback_trades: int = 20
    kelly_fraction: float = 0.25

SizerUnion = Annotated[
    Union[FractionalSizer, VolatilityScaling, KellyCriterion, DynamicKelly],
    Field(discriminator="type"),
]


class EnhancementsModel(BaseModel):
    filters: Optional[List[FilterUnion]] = None
    position_sizers: Optional[List[SizerUnion]] = None