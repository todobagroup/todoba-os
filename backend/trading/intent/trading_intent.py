"""
TODOBA Trading Intent

Represents the trading intention before execution.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TradingIntent:

    action: str

    asset: str

    sl: float

    tp: float

    entry: Optional[float] = None