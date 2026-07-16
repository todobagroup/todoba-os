"""
TODOBA Position Sizing Request

Represents one proposed trade evaluated by the
Risk Department.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionSizingRequest:
    """
    Immutable trade proposal evaluated by the
    Position Sizing Engine.

    This object intentionally contains no Broker,
    MT5, Telegram, or Strategy implementation.
    """

    account_equity: float

    symbol: str

    order_type: str

    entry_price: float

    stop_loss: float

    minimum_volume: float

    volume_step: float

    maximum_volume: float