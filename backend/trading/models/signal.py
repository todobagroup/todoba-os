"""
TODOBA Trading Signal Model

Represents a trading signal received from any signal source.

Version: 1.1
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Signal:
    """
    Immutable trading signal.

    Signal describes trade intent only.
    It does not decide lot, account, broker, or execution permission.
    """

    order_type: str
    symbol: str
    sl: float
    tp: float
    entry: Optional[float] = None