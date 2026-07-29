"""
TODOBA Execution Mission Lifecycle Service

Coordinates execution mission lifecycle updates.

This component does not:
- receive HTTP requests
- store acknowledgement evidence
- execute broker orders
"""

from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)

from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)

from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


class ExecutionMissionLifecycleService:
    """
    Service responsible for mission lifecycle coordination.
    """

    def __init__(
        self,
        registry: ExecutionMissionRegistry,
    ) -> None:

        if not isinstance(
            registry,
            ExecutionMissionRegistry,
        ):
            raise TypeError(
                "ExecutionMissionLifecycleService "
                "requires ExecutionMissionRegistry."
            )

        self.registry = registry

    def acknowledge(
        self,
        mission_id: str,
        acknowledged_at: str,
    ) -> ExecutionMissionRecord:

        record = self.registry.get(
            mission_id
        )

        if record is None:
            raise ValueError(
                "Execution mission record not found."
            )

        record.status = (
            ExecutionMissionStatus.ACKNOWLEDGED
        )

        record.acknowledged_at = (
            acknowledged_at
        )

        return record

    def start_execution(
        self,
        mission_id: str,
        started_at: str,
    ) -> ExecutionMissionRecord:

        record = self.registry.get(
            mission_id
        )

        if record is None:
            raise ValueError(
                "Execution mission record not found."
            )

        record.status = (
            ExecutionMissionStatus.EXECUTING
        )

        record.started_at = (
            started_at
        )

        return record

    def complete_execution(
        self,
        mission_id: str,
        completed_at: str,
    ) -> ExecutionMissionRecord:

        record = self.registry.get(
            mission_id
        )

        if record is None:
            raise ValueError(
                "Execution mission record not found."
            )

        record.status = (
            ExecutionMissionStatus.COMPLETED
        )

        record.completed_at = (
            completed_at
        )

        return record

    def fail_execution(
        self,
        mission_id: str,
        failed_at: str,
        failure_reason: str,
    ) -> ExecutionMissionRecord:

        record = self.registry.get(
            mission_id
        )

        if record is None:
            raise ValueError(
                "Execution mission record not found."
            )

        record.status = (
            ExecutionMissionStatus.FAILED
        )

        record.failed_at = (
            failed_at
        )

        record.failure_reason = (
            failure_reason
        )

        return record