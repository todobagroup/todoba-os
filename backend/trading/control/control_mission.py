"""
TODOBA Control Mission

Defines the broker-independent control mission contract
used across the remote control boundary.

The mission contains control intent only.
Transport, authentication, signing, lifecycle tracking,
and broker control belong to separate capabilities.
"""

from dataclasses import dataclass

from backend.trading.control.control_action import (
    ControlAction,
)


@dataclass(frozen=True)
class ControlMission:
    """
    Immutable remote trading control mission.

    This contract may be serialized by TODOBA Cloud and
    consumed by a Trusted Execution Agent.
    """

    mission_id: str
    agent_id: str
    account_fingerprint: str

    action: ControlAction

    symbol: str
    magic_number: int

    requested_by_sender_id: int

    created_at: str
    expires_at: str

    sequence: int
    security_sequence: int = 0