"""
TODOBA Execution Request

Represents a broker-ready trading request.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ExecutionRequest:

    action: str

    symbol: str

    order_type: str

    volume: float

    price: Optional[float]

    sl: float

    tp: float

    deviation: int

    magic_number: int

    comment: str