"""
TODOBA Execution Mission Status

Lifecycle states for remote execution missions.

These states describe the mission boundary between
TODOBA Cloud and Trusted Execution Agents.
"""

from enum import Enum


class ExecutionMissionStatus(Enum):
    """
    Execution mission lifecycle states.
    """

    CREATED = "CREATED"

    QUEUED = "QUEUED"

    DELIVERED = "DELIVERED"

    ACKNOWLEDGED = "ACKNOWLEDGED"

    EXECUTING = "EXECUTING"

    COMPLETED = "COMPLETED"

    FAILED = "FAILED"