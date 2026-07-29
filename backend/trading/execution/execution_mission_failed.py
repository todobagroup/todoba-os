"""
TODOBA Execution Mission Failed

Represents evidence that a Trusted Agent
has failed processing an execution mission.

This capability records failure evidence only.

It does not:
- execute broker orders
- own broker failure results
- modify mission lifecycle directly
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionMissionFailed:
    """
    Immutable execution failure evidence.
    """

    mission_id: str

    agent_id: str

    sequence: int

    failed_at: str

    failure_reason: str