"""
TODOBA Production Event

Represents one immutable production event.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ProductionEvent:
    """
    One production event emitted by TODOBA.
    """

    level: str
    department: str
    message: str

    context: dict[str, Any] = field(
        default_factory=dict
    )

    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(
            UTC
        )
    )