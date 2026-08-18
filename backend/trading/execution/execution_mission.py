"""
TODOBA Execution Mission

Defines the broker-independent mission contract used
across the remote execution boundary.

The mission contains execution intent only.
Transport, authentication, signing, and broker execution
belong to separate capabilities.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ExecutionMission:
    """
    Immutable remote execution mission.

    This contract may be serialized by TODOBA Cloud and
    consumed by a Trusted Execution Agent.
    """

    mission_id: str
    agent_id: str
    account_fingerprint: str

    symbol: str
    order_type: str

    volume: float
    entry: Optional[float]

    sl: float
    tp: float

    magic_number: int
    comment: str

    created_at: str
    expires_at: str

    sequence: int
    security_sequence: int = 0