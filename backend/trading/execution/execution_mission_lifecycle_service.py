"""
TODOBA Execution Mission Lifecycle Service

Coordinates execution mission lifecycle updates.

This component owns:
- lifecycle state transitions
- delivery attempt tracking
- mission record persistence after transitions

This component does not:
- receive HTTP requests
- store acknowledgement evidence
- execute broker orders
"""

from typing import Optional

from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_record_persistence import (
    ExecutionMissionRecordPersistence,
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
        record_persistence: Optional[
            ExecutionMissionRecordPersistence
        ] = None,
    ) -> None:
        if not isinstance(
            registry,
            ExecutionMissionRegistry,
        ):
            raise TypeError(
                "ExecutionMissionLifecycleService "
                "requires ExecutionMissionRegistry."
            )

        if (
            record_persistence is not None
            and not isinstance(
                record_persistence,
                ExecutionMissionRecordPersistence,
            )
        ):
            raise TypeError(
                "record_persistence must be "
                "ExecutionMissionRecordPersistence."
            )

        self.registry = registry
        self.record_persistence = record_persistence

    def _persist_records(
        self,
    ) -> None:
        if self.record_persistence is not None:
            self.record_persistence.save(
                self.registry
            )

    def mark_delivered(
        self,
        mission_id: str,
        delivered_at: str,
    ) -> ExecutionMissionRecord:
        record = self.registry.get(
            mission_id
        )

        if record is None:
            raise ValueError(
                "Execution mission record not found."
            )

        record.status = (
            ExecutionMissionStatus.DELIVERED
        )

        record.delivered_at = delivered_at

        record.delivery_attempt_count += 1

        self._persist_records()

        return record

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

        record.acknowledged_at = acknowledged_at

        self._persist_records()

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

        record.started_at = started_at

        self._persist_records()

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

        record.completed_at = completed_at

        self._persist_records()

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

        record.failed_at = failed_at

        record.failure_reason = failure_reason

        self._persist_records()

        return record