"""
TODOBA Execution Mission Record

Organizational record for one execution mission.

This record owns mission lifecycle tracking.

It does not modify the ExecutionMission contract.
It does not execute broker orders.
"""

from dataclasses import dataclass
from typing import Optional

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


@dataclass
class ExecutionMissionRecord:
    """
    Mutable organizational record for a mission.

    ExecutionMission remains immutable.
    This object tracks lifecycle state around it.
    """

    mission: ExecutionMission

    status: ExecutionMissionStatus = (
        ExecutionMissionStatus.CREATED
    )

    delivered_at: Optional[str] = None

    acknowledged_at: Optional[str] = None

    started_at: Optional[str] = None

    completed_at: Optional[str] = None

    failed_at: Optional[str] = None

    failure_reason: Optional[str] = None