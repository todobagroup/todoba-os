from dataclasses import replace
from pathlib import Path

import pytest

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_delivery_bridge import (
    ControlMissionDeliveryBridge,
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
from backend.trading.control.control_mission_service import (
    ControlMissionService,
)
from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
)
from backend.trading.control.control_mission_store import (
    ControlMissionStore,
)


MISSION_ID = "control-service-001"


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


def build_stack(
    tmp_path: Path,
) -> tuple[
    ControlMissionService,
    ControlMissionRepository,
    ControlMissionPersistence,
    ControlMissionRegistry,
    ControlMissionRecordPersistence,
    ControlMissionStore,
]:
    repository = ControlMissionRepository()
    persistence = ControlMissionPersistence(
        tmp_path / "control_missions.json"
    )
    registry = ControlMissionRegistry()
    record_persistence = ControlMissionRecordPersistence(
        tmp_path / "control_mission_records.json"
    )
    store = ControlMissionStore()
    delivery_bridge = ControlMissionDeliveryBridge(
        store
    )
    lifecycle_service = ControlMissionLifecycleService(
        registry,
        record_persistence,
        repository=repository,
        mission_persistence=persistence,
    )
    service = ControlMissionService(
        repository,
        persistence,
        delivery_bridge,
        registry,
        lifecycle_service,
    )

    return (
        service,
        repository,
        persistence,
        registry,
        record_persistence,
        store,
    )


def test_service_persists_queues_and_delivers_mission(
    tmp_path: Path,
) -> None:
    (
        service,
        repository,
        persistence,
        registry,
        record_persistence,
        store,
    ) = build_stack(
        tmp_path
    )
    mission = build_mission()

    result = service.create_mission(
        mission
    )

    assert result == mission
    assert repository.get(
        MISSION_ID
    ) == mission
    assert registry.get(
        MISSION_ID
    ).status == ControlMissionStatus.QUEUED
    assert store.pop_for_agent(
        "trusted-agent-001"
    ) == mission

    restored_repository = ControlMissionRepository()
    assert persistence.restore(
        restored_repository
    ) == 1
    assert restored_repository.get(
        MISSION_ID
    ) == mission

    restored_registry = ControlMissionRegistry()
    assert record_persistence.restore(
        restored_registry
    ) == 1
    assert restored_registry.get(
        MISSION_ID
    ).status == ControlMissionStatus.QUEUED


def test_service_retry_does_not_duplicate_mission(
    tmp_path: Path,
) -> None:
    service, repository, _, registry, _, store = (
        build_stack(
            tmp_path
        )
    )
    mission = build_mission()

    first = service.create_mission(
        mission
    )
    second = service.create_mission(
        mission
    )

    assert first == mission
    assert second == mission
    assert repository.size() == 1
    assert registry.size() == 1
    assert store.size() == 1


def test_service_repairs_existing_created_record(
    tmp_path: Path,
) -> None:
    service, repository, _, registry, _, store = (
        build_stack(
            tmp_path
        )
    )
    mission = build_mission()
    registry.register(
        ControlMissionRecord(
            mission=mission
        )
    )

    result = service.create_mission(
        mission
    )

    assert result == mission
    assert repository.get(
        MISSION_ID
    ) == mission
    assert registry.get(
        MISSION_ID
    ).status == ControlMissionStatus.QUEUED
    assert store.size() == 1


def test_service_does_not_redeliver_delivered_mission(
    tmp_path: Path,
) -> None:
    service, repository, _, registry, _, store = (
        build_stack(
            tmp_path
        )
    )
    mission = build_mission()
    repository.save(
        mission
    )
    registry.register(
        ControlMissionRecord(
            mission=mission,
            status=ControlMissionStatus.DELIVERED,
        )
    )

    result = service.create_mission(
        mission
    )

    assert result == mission
    assert store.size() == 0
    assert registry.get(
        MISSION_ID
    ).status == ControlMissionStatus.DELIVERED


def test_terminal_retry_does_not_resurrect_mission(
    tmp_path: Path,
) -> None:
    service, repository, _, registry, _, store = (
        build_stack(
            tmp_path
        )
    )
    mission = build_mission()
    registry.register(
        ControlMissionRecord(
            mission=mission,
            status=ControlMissionStatus.COMPLETED,
            completed_at="2026-08-15T00:00:10Z",
        )
    )

    result = service.create_mission(
        mission
    )

    assert result == mission
    assert repository.size() == 0
    assert store.size() == 0


def test_service_rejects_conflicting_mission_id(
    tmp_path: Path,
) -> None:
    service, _, _, _, _, _ = build_stack(
        tmp_path
    )
    mission = build_mission()
    service.create_mission(
        mission
    )
    conflicting = replace(
        mission,
        action=ControlAction.CLOSE_RED,
    )

    with pytest.raises(
        ValueError,
        match="Control mission ID conflict",
    ):
        service.create_mission(
            conflicting
        )


def test_service_rejects_invalid_mission(
    tmp_path: Path,
) -> None:
    service, _, _, _, _, _ = build_stack(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match="create_mission requires ControlMission",
    ):
        service.create_mission(
            "not-a-mission"
        )