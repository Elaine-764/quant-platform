from dataclasses import dataclass, field
from typing import Callable, Type, List, Dict, Any
from pydantic import BaseModel

@dataclass
class StrategySpec:
    model: Type[BaseModel]              # the Pydantic model for this strategy's params
    factory: Callable                    # (params, price_data, enhancements) -> Strategy instance
    asset_fields: List[str] = field(default_factory=list)        # single-ticker fields
    multi_asset_fields: List[str] = field(default_factory=list)  # List[str] ticker fields

REGISTRY: Dict[str, StrategySpec] = {}

def register_strategy(name: str, model: Type[BaseModel], asset_fields=None, multi_asset_fields=None):
    def decorator(factory: Callable):
        REGISTRY[name] = StrategySpec(
            model=model,
            factory=factory,
            asset_fields=asset_fields or [],
            multi_asset_fields=multi_asset_fields or [],
        )
        return factory
    return decorator