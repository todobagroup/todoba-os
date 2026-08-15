"""
TODOBA Control Mission Lifecycle Service

Coordinates control mission lifecycle updates.

Responsibilities:

- enforce valid lifecycle transitions
- track delivery attempts
- persist control records
- record broker control result counts
- remove terminal missions from active persistence
- release acknowledged or terminal delivery leases

This component does not receive HTTP requests, deliver
missions, or control broker trades.
"""

from typing import Optional

from backend.trading.control.control_mission_delivery_lease_persistence import (
    ControlMissionDeliveryLeasePersistence,
)
from backend.trading.control.control_mission_delivery_lease_registry import (
    ControlMissionDeliveryLeaseRegistry,
)
from backend.trading.control.control_mission_persistence import (
    ControlMissionPersistence,
)
from backend.trading.control.control_mission_record import (
    ControlMissionRecord,
)
from backend.trading.control.control_mission_record_persistence import (
    ControlMissionRecordPersistence,
)
from backend.trading.control.control_mission_registry import (
    ControlMissionRegistry,
)
from backend.trading.control.control_mission_repository import (
    ControlMissionRepository,
)
from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
)


class ControlMissionLifecycleService:
    """
    Service responsible for control mission lifecycle
    coordination and delivery lease release.
    """

    def __init__(
        self,
        registry: ControlMissionRegistry,
        record_persistence: Optional[
            ControlMissionRecordPersistence
        ] = None,
        *,
        repository: Optional[
            ControlMissionRepository
        ] = None,
        mission_persistence: Optional[
            ControlMissionPersistence
        ] = None,
        lease_registry: Optional[
            ControlMissionDeliveryLeaseRegistry
        ] = None,
        lease_persistence: Optional[
            ControlMissionDeliveryLeasePersistence
        ] = None,
    ) -> None:
        if not isinstance(
            registry,
            ControlMissionRegistry,
        ):
            raise TypeError(
                "ControlMissionLifecycleService requires "
                "ControlMissionRegistry."
            )

        if (
            record_persistence is not None
            and not isinstance(
                record_persistence,
                ControlMissionRecordPersistence,
            )
        ):
            raise TypeError(
                "record_persistence must be "
                "ControlMissionRecordPersistence."
            )

        if (
            repository is not None
            and not isinstance(
                repository,
                ControlMissionRepository,
            )
        ):
            raise TypeError(
                "repository must be "
                "ControlMissionRepository."
            )

        if (
            mission_persistence is not None
            and not isinstance(
                mission_persistence,
                ControlMissionPersistence,
            )
        ):
            raise TypeError(
                "mission_persistence must be "
                "ControlMissionPersistence."
            )

        if (
            mission_persistence is not None
            and repository is None
        ):
            raise ValueError(
                "mission_persistence requires repository."
            )

        if (
            lease_registry is not None
            and not isinstance(
                lease_registry,
                ControlMissionDeliveryLeaseRegistry,
            )
        ):
            raise TypeError(
                "lease_registry must be "
                "ControlMissionDeliveryLeaseRegistry."
            )

        if (
            lease_persistence is not None
            and not isinstance(
                lease_persistence,
                ControlMissionDeliveryLeasePersistence,
            )
        ):
            raise TypeError(
                "lease_persistence must be "
                "ControlMissionDeliveryLeasePersistence."
            )

        if (
            lease_persistence is not None
            and lease_registry is None
        ):
            raise ValueError(
                "lease_persistence requires lease_registry."
            )

        self.registry = registry
        self.record_persistence = record_persistence
        self.repository = repository
        self.mission_persistence = mission_persistence
        self.lease_registry = lease_registry
        self.lease_persistence = lease_persistence

    def _get_record(
        self,
        mission_id: str,
    ) -> ControlMissionRecord:
        record = self.registry.get(
            mission_id
        )

        if record is None:
            raise ValueError(
                "Control mission record not found."
            )

        return record

    def _persist_records(self) -> None:
        if self.record_persistence is not None:
            self.record_persistence.save(
                self.registry
            )

    def _cleanup_terminal_mission(
        self,
        mission_id: str,
    ) -> None:
        if self.repository is not None:
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

        self._release_delivery_lease(
            mission_id
        )

    def _release_delivery_lease(
        self,
        mission_id: str,
    ) -> None:
        if self.lease_registry is None:
            return

        released = self.lease_registry.release(
            mission_id
        )

        if (
            released is None
            or self.lease_persistence is None
        ):
            return

        try:
            self.lease_persistence.save(
                self.lease_registry
            )
        except Exception:
            self.lease_registry.acquire(
                released
            )
            raise

    @staticmethod
    def _require_transition(
        record: ControlMissionRecord,
        *,
        allowed: tuple[ControlMissionStatus, ...],
        target: ControlMissionStatus,
    ) -> None:
        if record.status not in allowed:
            raise ValueError(
                "Invalid control mission transition: "
                f"{record.status.value} -> {target.value}."
            )

    @staticmethod
    def _validate_count(
        name: str,
        value: int,
    ) -> None:
        if (
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
        ):
            raise TypeError(
                f"{name} must be int."
            )

        if value < 0:
            raise ValueError(
                f"{name} cannot be negative."
            )

    @classmethod
    def _validate_result_counts(
        cls,
        *,
        matched_position_count: int,
        closed_position_count: int,
        matched_pending_order_count: int,
        canceled_pending_order_count: int,
        failed_item_count: int,
    ) -> None:
        counts = {
            "matched_position_count": (
                matched_position_count
            ),
            "closed_position_count": (
                closed_position_count
            ),
            "matched_pending_order_count": (
                matched_pending_order_count
            ),
            "canceled_pending_order_count": (
                canceled_pending_order_count
            ),
            "failed_item_count": failed_item_count,
        }

        for name, value in counts.items():
            cls._validate_count(
                name,
                value,
            )

        if closed_position_count > matched_position_count:
            raise ValueError(
                "closed_position_count cannot exceed "
                "matched_position_count."
            )

        if (
            canceled_pending_order_count
            > matched_pending_order_count
        ):
            raise ValueError(
                "canceled_pending_order_count cannot "
                "exceed matched_pending_order_count."
            )

    @staticmethod
    def _apply_result_counts(
        record: ControlMissionRecord,
        *,
        matched_position_count: int,
        closed_position_count: int,
        matched_pending_order_count: int,
        canceled_pending_order_count: int,
        failed_item_count: int,
    ) -> None:
        record.matched_position_count = (
            matched_position_count
        )
        record.closed_position_count = (
            closed_position_count
        )
        record.matched_pending_order_count = (
            matched_pending_order_count
        )
        record.canceled_pending_order_count = (
            canceled_pending_order_count
        )
        record.failed_item_count = failed_item_count

    def queue(
        self,
        mission_id: str,
    ) -> ControlMissionRecord:
        record = self._get_record(
            mission_id
        )

        if record.status is ControlMissionStatus.QUEUED:
            return record

        self._require_transition(
            record,
            allowed=(ControlMissionStatus.CREATED,),
            target=ControlMissionStatus.QUEUED,
        )

        record.status = ControlMissionStatus.QUEUED

        self._persist_records()

        return record

    def mark_delivered(
        self,
        mission_id: str,
        delivered_at: str,
    ) -> ControlMissionRecord:
        record = self._get_record(
            mission_id
        )

        self._require_transition(
            record,
            allowed=(
                ControlMissionStatus.QUEUED,
                ControlMissionStatus.DELIVERED,
            ),
            target=ControlMissionStatus.DELIVERED,
        )

        record.status = ControlMissionStatus.DELIVERED
        record.delivered_at = delivered_at
        record.delivery_attempt_count += 1

        self._persist_records()

        return record

    def acknowledge(
        self,
        mission_id: str,
        acknowledged_at: str,
    ) -> ControlMissionRecord:
        record = self._get_record(
            mission_id
        )

        if record.status is ControlMissionStatus.ACKNOWLEDGED:
            self._release_delivery_lease(
                mission_id
            )
            return record

        self._require_transition(
            record,
            allowed=(ControlMissionStatus.DELIVERED,),
            target=ControlMissionStatus.ACKNOWLEDGED,
        )

        record.status = ControlMissionStatus.ACKNOWLEDGED
        record.acknowledged_at = acknowledged_at

        self._persist_records()
        self._release_delivery_lease(
            mission_id
        )

        return record

    def start_execution(
        self,
        mission_id: str,
        started_at: str,
    ) -> ControlMissionRecord:
        record = self._get_record(
            mission_id
        )

        if record.status is ControlMissionStatus.EXECUTING:
            return record

        self._require_transition(
            record,
            allowed=(ControlMissionStatus.ACKNOWLEDGED,),
            target=ControlMissionStatus.EXECUTING,
        )

        record.status = ControlMissionStatus.EXECUTING
        record.started_at = started_at

        self._persist_records()

        return record

    def complete_execution(
        self,
        mission_id: str,
        completed_at: str,
        *,
        matched_position_count: int,
        closed_position_count: int,
        matched_pending_order_count: int,
        canceled_pending_order_count: int,
    ) -> ControlMissionRecord:
        record = self._get_record(
            mission_id
        )

        self._validate_result_counts(
            matched_position_count=matched_position_count,
            closed_position_count=closed_position_count,
            matched_pending_order_count=(
                matched_pending_order_count
            ),
            canceled_pending_order_count=(
                canceled_pending_order_count
            ),
            failed_item_count=0,
        )

        if closed_position_count != matched_position_count:
            raise ValueError(
                "completed control mission must close all "
                "matched positions."
            )

        if (
            canceled_pending_order_count
            != matched_pending_order_count
        ):
            raise ValueError(
                "completed control mission must cancel all "
                "matched pending orders."
            )

        if record.status is ControlMissionStatus.COMPLETED:
            if (
                record.completed_at == completed_at
                and record.matched_position_count
                == matched_position_count
                and record.closed_position_count
                == closed_position_count
                and record.matched_pending_order_count
                == matched_pending_order_count
                and record.canceled_pending_order_count
                == canceled_pending_order_count
                and record.failed_item_count == 0
            ):
                self._release_delivery_lease(
                    mission_id
                )
                return record

            raise ValueError(
                "Completed control mission result conflict."
            )

        self._require_transition(
            record,
            allowed=(ControlMissionStatus.EXECUTING,),
            target=ControlMissionStatus.COMPLETED,
        )

        record.status = ControlMissionStatus.COMPLETED
        record.completed_at = completed_at

        self._apply_result_counts(
            record,
            matched_position_count=matched_position_count,
            closed_position_count=closed_position_count,
            matched_pending_order_count=(
                matched_pending_order_count
            ),
            canceled_pending_order_count=(
                canceled_pending_order_count
            ),
            failed_item_count=0,
        )

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
        *,
        matched_position_count: int = 0,
        closed_position_count: int = 0,
        matched_pending_order_count: int = 0,
        canceled_pending_order_count: int = 0,
        failed_item_count: int = 0,
    ) -> ControlMissionRecord:
        record = self._get_record(
            mission_id
        )

        if (
            not isinstance(
                failure_reason,
                str,
            )
            or not failure_reason.strip()
        ):
            raise ValueError(
                "failure_reason is required."
            )

        self._validate_result_counts(
            matched_position_count=matched_position_count,
            closed_position_count=closed_position_count,
            matched_pending_order_count=(
                matched_pending_order_count
            ),
            canceled_pending_order_count=(
                canceled_pending_order_count
            ),
            failed_item_count=failed_item_count,
        )

        normalized_failure_reason = (
            failure_reason.strip()
        )

        if record.status is ControlMissionStatus.FAILED:
            if (
                record.failed_at == failed_at
                and record.failure_reason
                == normalized_failure_reason
                and record.matched_position_count
                == matched_position_count
                and record.closed_position_count
                == closed_position_count
                and record.matched_pending_order_count
                == matched_pending_order_count
                and record.canceled_pending_order_count
                == canceled_pending_order_count
                and record.failed_item_count
                == failed_item_count
            ):
                self._release_delivery_lease(
                    mission_id
                )
                return record

            raise ValueError(
                "Failed control mission result conflict."
            )

        if record.status is ControlMissionStatus.COMPLETED:
            self._require_transition(
                record,
                allowed=(),
                target=ControlMissionStatus.FAILED,
            )

        record.status = ControlMissionStatus.FAILED
        record.failed_at = failed_at
        record.failure_reason = normalized_failure_reason

        self._apply_result_counts(
            record,
            matched_position_count=matched_position_count,
            closed_position_count=closed_position_count,
            matched_pending_order_count=(
                matched_pending_order_count
            ),
            canceled_pending_order_count=(
                canceled_pending_order_count
            ),
            failed_item_count=failed_item_count,
        )

        self._persist_records()
        self._cleanup_terminal_mission(
            mission_id
        )

        return record