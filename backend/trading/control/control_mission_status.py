"""
TODOBA Control Mission Status

Lifecycle states for remote control missions.

These states describe the control boundary between
TODOBA Cloud and Trusted Execution Agents.
"""

from enum import Enum


class ControlMissionStatus(Enum):
    """
    Control mission lifecycle states.
    """

    CREATED = "CREATED"

    QUEUED = "QUEUED"

    DELIVERED = "DELIVERED"

    ACKNOWLEDGED = "ACKNOWLEDGED"

    EXECUTING = "EXECUTING"

    COMPLETED = "COMPLETED"

    FAILED = "FAILED"