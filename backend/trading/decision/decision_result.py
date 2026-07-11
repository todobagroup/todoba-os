"""
TODOBA Trading Decision Result
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionResult:

    approved: bool

    reason: str