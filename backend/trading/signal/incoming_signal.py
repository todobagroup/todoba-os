"""
TODOBA Incoming Signal

Represents a normalized signal received from external sources.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class IncomingSignal:
    """
    Standard signal format entering TODOBA.
    """

    source: str

    message: str

    received_at: datetime

    sender: Optional[str] = None