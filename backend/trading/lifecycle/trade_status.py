"""
TODOBA Trade Status
"""

from enum import Enum


class TradeStatus(Enum):

    CREATED = "CREATED"

    EXECUTING = "EXECUTING"

    OPEN = "OPEN"

    CLOSED = "CLOSED"