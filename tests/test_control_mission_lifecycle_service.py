from pathlib import Path

import pytest

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_delivery_lease import (
    ControlMissionDeliveryLease,
)
from backend.trading.control.control_mission_delivery_lease_persistence import (
    ControlMissionDeliveryLeasePersistence,
)
from backend.trading.control.control_mission_delivery_lease_registry import (
    ControlMissionDeliveryLeaseRegistry,
)
from backend.trading.control.control_mission_lifecycle_service import (
    ControlMissionLifecycleService,
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


MISSION_ID = "control-001"


def build_mission() -> ControlMission:
    return ControlMission(
        mission_id=MISSION_ID,
        agent_id="trusted-agent-001",
        account_fingerprint="account-test",
        action=ControlAction.FLATTEN_ALL,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=5414928751,
        created_at="2026-08-15T00:00:00Z",
        expires_at="2026-08-15T00:01:00Z",
        sequence=1,
    )


def build_service(
    tmp_path: Path,
) -> tuple[
    ControlMissionLifecycleService,
    ControlMissionRegistry,
    ControlMissionRepository,
    ControlMissionPersistence,
    ControlMissionRecordPersistence,
]:
    mission = build_mission()

    registry = ControlMissionRegistry()
    registry.register(
        ControlMissionRecord(
            mission=mission
        )
    )

    repository = ControlMissionRepository()
    repository.save(
        mission
    )

    mission_persistence = ControlMissionPersistence(
        tmp_path
        / "control_missions.json"
    )
    mission_persistence.save(
        repository
    )

    record_persistence = ControlMissionRecordPersistence(
        tmp_path
        / "control_mission_records.json"
    )

    lease_registry = ControlMissionDeliveryLeaseRegistry()
    lease_persistence = ControlMissionDeliveryLeasePersistence(
        tmp_path
        / "control_mission_delivery_leases.json"
    )

    service = ControlMissionLifecycleService(
        registry,
        record_persistence,
        repository=repository,
        mission_persistence=mission_persistence,
        lease_registry=lease_registry,
        lease_persistence=lease_persistence,
    )

    return (
        service,
        registry,
        repository,
        mission_persistence,
        record_persistence,
    )


def advance_to_executing(
    service: ControlMissionLifecycleService,
) -> None:
    service.queue(
        MISSION_ID
    )
    service.mark_delivered(
        MISSION_ID,
        "2026-08-15T00:00:01Z",
    )
    service.acknowledge(
        MISSION_ID,
        "2026-08-15T00:00:02Z",
    )
    service.start_execution(
        MISSION_ID,
        "2026-08-15T00:00:03Z",
    )


def test_successful_lifecycle_persists_result_and_cleans_active_mission(
    tmp_path: Path,
) -> None:
    (
        service,
        registry,
        repository,
        mission_persistence,
        record_persistence,
    ) = build_service(
        tmp_path
    )

    advance_to_executing(
        service
    )

    result = service.complete_execution(
        MISSION_ID,
        "2026-08-15T00:00:04Z",
        matched_position_count=3,
        closed_position_count=3,
        matched_pending_order_count=2,
        canceled_pending_order_count=2,
    )

    assert result.status is ControlMissionStatus.COMPLETED
    assert result.closed_position_count == 3
    assert result.canceled_pending_order_count == 2
    assert result.failed_item_count == 0

    assert repository.get(
        MISSION_ID
    ) is None

    restored_repository = ControlMissionRepository()
    assert mission_persistence.restore(
        restored_repository
    ) == 0

    restored_registry = ControlMissionRegistry()
    assert record_persistence.restore(
        restored_registry
    ) == 1

    restored = restored_registry.get(
        MISSION_ID
    )

    assert restored is not None
    assert restored.status is ControlMissionStatus.COMPLETED
    assert restored.closed_position_count == 3
    assert registry.get(MISSION_ID) is result


def test_delivery_retry_increments_attempt_count(
    tmp_path: Path,
) -> None:
    service, registry, _, _, _ = build_service(
        tmp_path
    )

    service.queue(
        MISSION_ID
    )

    service.mark_delivered(
        MISSION_ID,
        "2026-08-15T00:00:01Z",
    )
    service.mark_delivered(
        MISSION_ID,
        "2026-08-15T00:00:06Z",
    )

    record = registry.get(
        MISSION_ID
    )

    assert record is not None
    assert record.delivery_attempt_count == 2
    assert record.delivered_at == "2026-08-15T00:00:06Z"


def test_non_delivery_callbacks_are_idempotent(
    tmp_path: Path,
) -> None:
    service, _, _, _, _ = build_service(
        tmp_path
    )

    service.queue(
        MISSION_ID
    )
    service.mark_delivered(
        MISSION_ID,
        "2026-08-15T00:00:01Z",
    )

    acknowledged = service.acknowledge(
        MISSION_ID,
        "2026-08-15T00:00:02Z",
    )

    assert service.acknowledge(
        MISSION_ID,
        "2026-08-15T00:00:02Z",
    ) is acknowledged

    executing = service.start_execution(
        MISSION_ID,
        "2026-08-15T00:00:03Z",
    )

    assert service.start_execution(
        MISSION_ID,
        "2026-08-15T00:00:03Z",
    ) is executing


def test_completed_callback_requires_identical_retry(
    tmp_path: Path,
) -> None:
    service, _, _, _, _ = build_service(
        tmp_path
    )
    advance_to_executing(
        service
    )

    completed = service.complete_execution(
        MISSION_ID,
        "2026-08-15T00:00:04Z",
        matched_position_count=1,
        closed_position_count=1,
        matched_pending_order_count=0,
        canceled_pending_order_count=0,
    )

    assert service.complete_execution(
        MISSION_ID,
        "2026-08-15T00:00:04Z",
        matched_position_count=1,
        closed_position_count=1,
        matched_pending_order_count=0,
        canceled_pending_order_count=0,
    ) is completed

    with pytest.raises(
        ValueError,
        match="result conflict",
    ):
        service.complete_execution(
            MISSION_ID,
            "2026-08-15T00:00:05Z",
            matched_position_count=1,
            closed_position_count=1,
            matched_pending_order_count=0,
            canceled_pending_order_count=0,
        )


def test_partial_success_cannot_be_completed(
    tmp_path: Path,
) -> None:
    service, _, _, _, _ = build_service(
        tmp_path
    )
    advance_to_executing(
        service
    )

    with pytest.raises(
        ValueError,
        match="close all matched positions",
    ):
        service.complete_execution(
            MISSION_ID,
            "2026-08-15T00:00:04Z",
            matched_position_count=3,
            closed_position_count=2,
            matched_pending_order_count=0,
            canceled_pending_order_count=0,
        )


def test_failure_records_partial_result_and_cleans_active_mission(
    tmp_path: Path,
) -> None:
    service, _, repository, _, _ = build_service(
        tmp_path
    )
    advance_to_executing(
        service
    )

    failed = service.fail_execution(
        MISSION_ID,
        "2026-08-15T00:00:04Z",
        "Broker rejected one close request.",
        matched_position_count=3,
        closed_position_count=2,
        matched_pending_order_count=1,
        canceled_pending_order_count=1,
        failed_item_count=1,
    )

    assert failed.status is ControlMissionStatus.FAILED
    assert failed.closed_position_count == 2
    assert failed.failed_item_count == 1
    assert repository.get(MISSION_ID) is None

    assert service.fail_execution(
        MISSION_ID,
        "2026-08-15T00:00:04Z",
        "Broker rejected one close request.",
        matched_position_count=3,
        closed_position_count=2,
        matched_pending_order_count=1,
        canceled_pending_order_count=1,
        failed_item_count=1,
    ) is failed

    with pytest.raises(
        ValueError,
        match="result conflict",
    ):
        service.fail_execution(
            MISSION_ID,
            "2026-08-15T00:00:04Z",
            "Different failure.",
            failed_item_count=1,
        )


def test_invalid_transition_is_rejected(
    tmp_path: Path,
) -> None:
    service, _, _, _, _ = build_service(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="CREATED -> ACKNOWLEDGED",
    ):
        service.acknowledge(
            MISSION_ID,
            "2026-08-15T00:00:02Z",
        )


def test_unknown_mission_is_rejected(
    tmp_path: Path,
) -> None:
    service, _, _, _, _ = build_service(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="record not found",
    ):
        service.queue(
            "missing-control"
        )


def test_acknowledgement_releases_and_persists_lease(
    tmp_path: Path,
) -> None:
    service, _, _, _, _ = build_service(
        tmp_path
    )
    lease_registry = service.lease_registry
    lease_persistence = service.lease_persistence
    assert lease_registry is not None
    assert lease_persistence is not None

    service.queue(
        MISSION_ID
    )
    service.mark_delivered(
        MISSION_ID,
        "2026-08-15T00:00:01Z",
    )
    lease_registry.acquire(
        ControlMissionDeliveryLease(
            mission_id=MISSION_ID,
            agent_id="trusted-agent-001",
            leased_at="2026-08-15T00:00:01Z",
            expires_at="2026-08-15T00:00:31Z",
        )
    )
    lease_persistence.save(
        lease_registry
    )

    service.acknowledge(
        MISSION_ID,
        "2026-08-15T00:00:02Z",
    )

    assert lease_registry.size() == 0
    restored = ControlMissionDeliveryLeaseRegistry()
    assert lease_persistence.restore(
        restored
    ) == 0


def test_terminal_failure_releases_lease_as_fallback(
    tmp_path: Path,
) -> None:
    service, _, _, _, _ = build_service(
        tmp_path
    )
    lease_registry = service.lease_registry
    assert lease_registry is not None

    service.queue(
        MISSION_ID
    )
    service.mark_delivered(
        MISSION_ID,
        "2026-08-15T00:00:01Z",
    )
    lease_registry.acquire(
        ControlMissionDeliveryLease(
            mission_id=MISSION_ID,
            agent_id="trusted-agent-001",
            leased_at="2026-08-15T00:00:01Z",
            expires_at="2026-08-15T00:00:31Z",
        )
    )

    service.fail_execution(
        MISSION_ID,
        "2026-08-15T00:00:02Z",
        "Agent failed before acknowledgement.",
        failed_item_count=1,
    )

    assert lease_registry.size() == 0


def test_lease_persistence_failure_restores_released_lease(
    tmp_path: Path,
) -> None:
    class FailingLeasePersistence(
        ControlMissionDeliveryLeasePersistence
    ):
        def save(self, registry) -> None:
            raise RuntimeError(
                "proof lease persistence failure"
            )

    service, _, _, _, _ = build_service(
        tmp_path
    )
    lease_registry = service.lease_registry
    assert lease_registry is not None

    service.queue(
        MISSION_ID
    )
    service.mark_delivered(
        MISSION_ID,
        "2026-08-15T00:00:01Z",
    )
    lease_registry.acquire(
        ControlMissionDeliveryLease(
            mission_id=MISSION_ID,
            agent_id="trusted-agent-001",
            leased_at="2026-08-15T00:00:01Z",
            expires_at="2026-08-15T00:00:31Z",
        )
    )
    service.lease_persistence = FailingLeasePersistence(
        tmp_path / "failing_leases.json"
    )

    with pytest.raises(
        RuntimeError,
        match="proof lease persistence failure",
    ):
        service.acknowledge(
            MISSION_ID,
            "2026-08-15T00:00:02Z",
        )

    assert lease_registry.size() == 1


def test_lease_persistence_requires_lease_registry(
    tmp_path: Path,
) -> None:
    lease_persistence = ControlMissionDeliveryLeasePersistence(
        tmp_path / "control_leases.json"
    )

    with pytest.raises(
        ValueError,
        match="lease_persistence requires lease_registry",
    ):
        ControlMissionLifecycleService(
            ControlMissionRegistry(),
            lease_persistence=lease_persistence,
        )