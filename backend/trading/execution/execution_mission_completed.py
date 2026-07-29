"""
TODOBA Execution Mission Completed

Represents evidence that a Trusted Agent
has completed processing an execution mission.

This capability records completion evidence only.

It does not:
- execute broker orders
- own broker results
- modify mission lifecycle directly
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionMissionCompleted:
    """
    Immutable execution completion evidence.
    """

    mission_id: str

    agent_id: str

    sequence: int

    completed_at: str