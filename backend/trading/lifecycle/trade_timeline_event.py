"""
TODOBA Trade Timeline Event

Represents one immutable event in the
lifecycle of a trade.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class TradeTimelineEvent:
    """
    One event in a trade timeline.
    """

    trade_id: str

    stage: str

    message: str

    context: dict[str, Any] = field(
        default_factory=dict
    )

    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(
            UTC
        )
    )