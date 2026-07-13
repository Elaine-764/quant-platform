from typing import Optional, Union
from pydantic import BaseModel


class EventModel(BaseModel):
    name: str


class MarketEventModel(EventModel):
    timestamp: int
    price: float


class SignalEventModel(EventModel):
    timestamp: int
    asset: Optional[str] = None
    signal: int


class FullSignalEventModel(EventModel):
    timestamp: int
    asset: Optional[str] = None
    signal: Union[str, int]
    size: float


class OrderEventModel(EventModel):
    timestamp: int
    asset: str
    price: float
    quantity: float
    direction: str


class FillEventModel(EventModel):
    timestamp: int
    asset: str
    quantity: float
    price: float

