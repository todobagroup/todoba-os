"""
TODOBA Pending Activation Result

Represents the result of evaluating whether
a pending order should activate into a trade.
"""

from dataclasses import dataclass
from typing import Optional

from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)


@dataclass(frozen=True)
class PendingActivationResult:
    """
    Immutable activation result.
    """

    activated: bool

    trade_record: Optional[TradeRecord] = None

    reason: Optional[str] = None