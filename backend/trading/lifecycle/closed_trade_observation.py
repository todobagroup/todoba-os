"""
TODOBA Closed Trade Observation

Represents broker evidence observed after a trading
position has been closed.

This is evidence, not yet an interpreted lesson.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class ClosedTradeObservation:
    """
    Immutable observation of a closed broker position.
    """

    position_id: int
    close_deal_id: int

    symbol: str
    action: str
    volume: float

    close_price: float
    closed_at: datetime

    gross_profit: float
    commission: float
    swap: float
    fee: float
    net_profit: float

    close_reason: str

    order_id: Optional[int] = None
    comment: str = ""
