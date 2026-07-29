"""
TODOBA Execution Mission Execution Started

Represents evidence that a Trusted Agent
has started executing an execution mission.

This capability records execution start evidence only.

It does not:
- execute broker orders
- own broker results
- modify mission lifecycle directly
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionMissionExecutionStarted:
    """
    Immutable execution start evidence.
    """

    mission_id: str

    agent_id: str

    sequence: int

    started_at: str