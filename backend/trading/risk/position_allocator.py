"""
TODOBA Position Allocator

Finds the largest broker volume that satisfies
the organizational risk budget.
"""

from abc import ABC
from abc import abstractmethod

from backend.trading.risk.position_sizing_request import (
    PositionSizingRequest,
)


class PositionAllocator(ABC):
    """
    Determines the broker volume to use for one trade.
    """

    @abstractmethod
    def allocate(
        self,
        *,
        request: PositionSizingRequest,
        risk_budget_money: float,
    ) -> float:
        """
        Return the broker volume that best matches
        the requested risk budget.
        """
        raise NotImplementedError