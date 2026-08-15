"""
TODOBA Trading Control Action

Defines the broker-independent actions allowed
through the Remote Trading Control boundary.
"""

from enum import Enum


class ControlAction(
    str,
    Enum,
):
    """
    Supported deterministic trading control actions.
    """

    CLOSE_GREEN = "CLOSE_GREEN"
    CLOSE_RED = "CLOSE_RED"

    CLOSE_BUY = "CLOSE_BUY"
    CLOSE_SELL = "CLOSE_SELL"

    CLOSE_ALL_POSITIONS = (
        "CLOSE_ALL_POSITIONS"
    )

    CANCEL_ALL_PENDING = (
        "CANCEL_ALL_PENDING"
    )

    FLATTEN_ALL = "FLATTEN_ALL"