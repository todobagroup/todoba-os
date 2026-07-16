"""
TODOBA Pending Order Status
"""

from enum import Enum


class PendingOrderStatus(Enum):
    """
    Lifecycle states of a pending order.
    """

    CREATED = "CREATED"

    PLACED = "PLACED"

    TRIGGERED = "TRIGGERED"

    CANCELLED = "CANCELLED"

    EXPIRED = "EXPIRED"