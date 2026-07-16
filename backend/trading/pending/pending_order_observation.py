"""
TODOBA Pending Order Observation

Immutable broker evidence describing the current
state of one organizational pending order.

This object contains broker evidence only.

It does not:
- modify PendingOrderRecord;
- create TradeRecord;
- change lifecycle;
- update repositories.
"""

from dataclasses import dataclass
from typing import Optional

from backend.trading.pending.pending_broker_status import (
    PendingBrokerStatus,
)


@dataclass(frozen=True)
class PendingOrderObservation:
    """
    Immutable broker evidence for one pending order.
    """

    pending_order_id: str

    order_ticket: Optional[int]

    status: PendingBrokerStatus

    broker_order_state: Optional[int] = None

    position_id: Optional[int] = None

    opening_deal_ticket: Optional[int] = None

    opening_deal_entry: Optional[int] = None

    opening_deal_type: Optional[int] = None

    active_order_found: bool = False

    historical_order_found: bool = False

    opening_deal_found: bool = False

    error: Optional[str] = None