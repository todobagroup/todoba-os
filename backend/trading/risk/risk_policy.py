"""
TODOBA Risk Policy

Defines configurable risk rules used by the
Risk Department.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskPolicy:
    """
    Immutable organizational risk policy.
    """

    risk_percent: float

    minimum_volume: float

    volume_step: float

    maximum_volume: float

    reject_when_minimum_volume_exceeds_risk: bool = True