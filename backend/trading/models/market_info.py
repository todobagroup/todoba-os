"""
TODOBA Market Information

Represents market data for one symbol.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketInfo:

    symbol: str

    bid: float

    ask: float

    spread: float

    digits: int

    point: float