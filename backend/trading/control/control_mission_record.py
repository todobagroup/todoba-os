"""
TODOBA Control Mission Record

Organizational record for one control mission.

This record owns lifecycle tracking and broker control
result counts. It never modifies the immutable
ControlMission contract and never controls broker trades.
"""

from dataclasses import dataclass
from typing import Optional

from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
)


@dataclass
class ControlMissionRecord:
    """
    Mutable organizational record for a control mission.
    """

    mission: ControlMission

    status: ControlMissionStatus = (
        ControlMissionStatus.CREATED
    )

    delivered_at: Optional[str] = None
    delivery_attempt_count: int = 0

    acknowledged_at: Optional[str] = None
    started_at: Optional[str] = None

    completed_at: Optional[str] = None
    failed_at: Optional[str] = None
    failure_reason: Optional[str] = None

    matched_position_count: int = 0
    closed_position_count: int = 0

    matched_pending_order_count: int = 0
    canceled_pending_order_count: int = 0

    failed_item_count: int = 0