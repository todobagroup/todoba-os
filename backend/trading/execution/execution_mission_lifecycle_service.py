"""
TODOBA Execution Mission Lifecycle Service

Coordinates execution mission lifecycle updates.

This component owns:

- lifecycle state transitions
- delivery attempt tracking
- mission record persistence after transitions
- terminal mission repository cleanup
- mission repository persistence after terminal cleanup

This component does not:

- receive HTTP requests
- store acknowledgement evidence
- execute broker orders
"""

from typing import Optional

from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_record_persistence import (
    ExecutionMissionRecordPersistence,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
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
        *,
        repository: Optional[
            ExecutionMissionRepository
        ] = None,
        mission_persistence: Optional[
            ExecutionMissionPersistence
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

        if (
            repository is not None
            and not isinstance(
                repository,
                ExecutionMissionRepository,
            )
        ):
            raise TypeError(
                "repository must be "
                "ExecutionMissionRepository."
            )

        if (
            mission_persistence is not None
            and not isinstance(
                mission_persistence,
                ExecutionMissionPersistence,
            )
        ):
            raise TypeError(
                "mission_persistence must be "
                "ExecutionMissionPersistence."
            )

        if (
            mission_persistence is not None
            and repository is None
        ):
            raise ValueError(
                "mission_persistence requires repository."
            )

        self.registry = registry
        self.record_persistence = record_persistence
        self.repository = repository
        self.mission_persistence = mission_persistence

    def _persist_records(
        self,
    ) -> None:
        if self.record_persistence is not None:
            self.record_persistence.save(
                self.registry
            )

    def _cleanup_terminal_mission(
        self,
        mission_id: str,
    ) -> None:
        if self.repository is None:
            return

        removed = self.repository.remove(
            mission_id
        )

        if (
            removed
            and self.mission_persistence is not None
        ):
            self.mission_persistence.save(
                self.repository
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

        self._cleanup_terminal_mission(
            mission_id
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

        record.failed_at = failed_at

        record.failure_reason = failure_reason

        self._persist_records()

        self._cleanup_terminal_mission(
            mission_id
        )

        return record