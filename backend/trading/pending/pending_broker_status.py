"""
TODOBA Pending Broker Status

Broker evidence states for one pending order.

These states describe broker observations only.

They are NOT organizational lifecycle states.
"""

from enum import Enum


class PendingBrokerStatus(Enum):
    """
    Broker evidence states.

    These values come from broker evidence.

    They do not modify PendingOrderRecord.
    """

    ACTIVE = "ACTIVE"

    FILLED = "FILLED"

    CANCELLED = "CANCELLED"

    EXPIRED = "EXPIRED"

    REJECTED = "REJECTED"

    UNKNOWN = "UNKNOWN"