"""Strategy enhancements for filters, position sizing, and risk controls."""

from .filters import (
    Filter,
    VolatilityFilter,
    MomentumFilter,
    VolumeFilter,
    CompositeFilter,
)

from .position_resizing import (
    PositionSizer,
    VolatilityScaling,
    KellyCriterion,
    DynamicKelly,
)

# from .risk_controls import (
#     RiskControl,
#     StopLoss,
#     MaxDrawdownControl,
#     MaxPositionSize,
#     ConsecutiveLossControl,
#     TimeBasedControl,
#     CompositeRiskControl,
# )

__all__ = [
    'Filter',
    'VolatilityFilter',
    'MomentumFilter',
    'VolumeFilter',
    'CompositeFilter',
    'PositionSizer',
    'FixedPositionSizer',
    'VolatilityScaling',
    'KellyCriterion',
    'DynamicKelly',
    'RiskControl',
    'StopLoss',
    'MaxDrawdownControl',
    'MaxPositionSize',
    'ConsecutiveLossControl',
    'TimeBasedControl',
    'CompositeRiskControl',
]
