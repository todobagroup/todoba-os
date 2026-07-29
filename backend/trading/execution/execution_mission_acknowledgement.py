"""
TODOBA Execution Mission Acknowledgement

Represents evidence that a Trusted Agent
has received and accepted an execution mission.

This capability records agent acknowledgement only.

It does not execute orders.
It does not own broker results.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionMissionAcknowledgement:
    """
    Immutable acknowledgement evidence
    created by a Trusted Agent.
    """

    mission_id: str

    agent_id: str

    sequence: int

    status: str

    acknowledged_at: str