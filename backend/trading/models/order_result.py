"""
TODOBA Order Result

Represents the normalized result of a broker order execution.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class OrderResult:

    success: bool

    retcode: int

    order: Optional[int]

    deal: Optional[int]

    volume: float

    price: float

    comment: str