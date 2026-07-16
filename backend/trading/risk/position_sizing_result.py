"""
TODOBA Position Sizing Result

Represents the final decision produced by
the Position Sizing Engine.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionSizingResult:
    """
    Final output of the Risk Department.

    Trading Department only consumes this object.
    """

    approved: bool

    volume: float

    estimated_risk_money: float

    estimated_risk_percent: float

    reason: str