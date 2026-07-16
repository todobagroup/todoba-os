"""
TODOBA Pending Order Record
"""

from dataclasses import dataclass

from backend.trading.pending.pending_order_status import (
    PendingOrderStatus,
)


@dataclass
class PendingOrderRecord:
    """
    Represents one pending order owned by TODOBA.
    """

    pending_order_id: str

    symbol: str

    order_type: str

    volume: float

    entry: float

    sl: float

    tp: float

    status: PendingOrderStatus

    order: int | None = None