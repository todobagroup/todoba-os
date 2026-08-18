from pathlib import Path

import pytest

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)
from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)
from backend.trading.execution.execution_mission_service import (
    ExecutionMissionService,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)


MISSION_ID = "execution-retry-safety-001"
AGENT_ID = "trusted-agent-001"


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Retry Safety",
        created_at="2026-08-18T12:00:00Z",
        expires_at="2026-08-18T13:00:00Z",
        sequence=1,
    )


def build_stack(
    tmp_path: Path,
) -> tuple[
    ExecutionMissionService,
    ExecutionMissionRepository,
    ExecutionMissionPersistence,
    ExecutionMissionRegistry,
    ExecutionMissionStore,
]:
    repository = ExecutionMissionRepository()

    persistence = ExecutionMissionPersistence(
        tmp_path / "execution_missions.json"
    )

    registry = ExecutionMissionRegistry()

    store = ExecutionMissionStore()

    delivery_bridge = ExecutionMissionDeliveryBridge(
        store
    )

    service = ExecutionMissionService(
        repository,
        persistence,
        delivery_bridge,
        registry,
    )

    return (
        service,
        repository,
        persistence,
        registry,
        store,
    )


def test_identical_retry_preserves_existing_created_record(
    tmp_path: Path,
) -> None:
    (
        service,
        repository,
        _,
        registry,
        store,
    ) = build_stack(
        tmp_path
    )

    mission = build_mission()

    first = service.create_mission(
        mission
    )

    existing_record = registry.get(
        MISSION_ID
    )

    second = service.create_mission(
        mission
    )

    assert first == mission
    assert second == mission

    assert registry.get(
        MISSION_ID
    ) is existing_record

    assert registry.get(
        MISSION_ID
    ).status == ExecutionMissionStatus.CREATED

    assert repository.size() == 1
    assert store.size() == 1


def test_created_retry_repairs_missing_queue_without_replacing_record(
    tmp_path: Path,
) -> None:
    (
        service,
        _,
        _,
        registry,
        store,
    ) = build_stack(
        tmp_path
    )

    mission = build_mission()

    service.create_mission(
        mission
    )

    existing_record = registry.get(
        MISSION_ID
    )

    delivered = store.pop_for_agent(
        AGENT_ID
    )

    assert delivered == mission
    assert store.size() == 0

    result = service.create_mission(
        mission
    )

    assert result == mission

    assert registry.get(
        MISSION_ID
    ) is existing_record

    assert registry.get(
        MISSION_ID
    ).status == ExecutionMissionStatus.CREATED

    assert store.size() == 1

    assert store.pop_for_agent(
        AGENT_ID
    ) == mission


@pytest.mark.parametrize(
    "target_status",
    [
        ExecutionMissionStatus.DELIVERED,
        ExecutionMissionStatus.EXECUTING,
    ],
)
def test_retry_does_not_reset_active_lifecycle(
    tmp_path: Path,
    target_status: ExecutionMissionStatus,
) -> None:
    (
        service,
        _,
        _,
        registry,
        store,
    ) = build_stack(
        tmp_path
    )

    mission = build_mission()

    service.create_mission(
        mission
    )

    assert store.pop_for_agent(
        AGENT_ID
    ) == mission

    lifecycle = ExecutionMissionLifecycleService(
        registry
    )

    lifecycle.mark_delivered(
        MISSION_ID,
        "2026-08-18T12:01:00Z",
    )

    if target_status == ExecutionMissionStatus.EXECUTING:
        lifecycle.start_execution(
            MISSION_ID,
            "2026-08-18T12:02:00Z",
        )

    existing_record = registry.get(
        MISSION_ID
    )

    result = service.create_mission(
        mission
    )

    assert result == mission

    assert registry.get(
        MISSION_ID
    ) is existing_record

    assert registry.get(
        MISSION_ID
    ).status == target_status

    assert store.size() == 0


@pytest.mark.parametrize(
    "terminal_status",
    [
        ExecutionMissionStatus.COMPLETED,
        ExecutionMissionStatus.FAILED,
    ],
)
def test_terminal_retry_does_not_resurrect_execution_mission(
    tmp_path: Path,
    terminal_status: ExecutionMissionStatus,
) -> None:
    (
        service,
        repository,
        persistence,
        registry,
        store,
    ) = build_stack(
        tmp_path
    )

    mission = build_mission()

    service.create_mission(
        mission
    )

    assert store.pop_for_agent(
        AGENT_ID
    ) == mission

    lifecycle = ExecutionMissionLifecycleService(
        registry,
        repository=repository,
        mission_persistence=persistence,
    )

    lifecycle.mark_delivered(
        MISSION_ID,
        "2026-08-18T12:01:00Z",
    )

    if terminal_status == ExecutionMissionStatus.COMPLETED:
        lifecycle.complete_execution(
            MISSION_ID,
            "2026-08-18T12:02:00Z",
        )
    else:
        lifecycle.fail_execution(
            MISSION_ID,
            "2026-08-18T12:02:00Z",
            "proof failure",
        )

    existing_record = registry.get(
        MISSION_ID
    )

    assert existing_record.status == terminal_status
    assert repository.size() == 0
    assert store.size() == 0

    result = service.create_mission(
        mission
    )

    assert result == mission

    assert registry.get(
        MISSION_ID
    ) is existing_record

    assert registry.get(
        MISSION_ID
    ).status == terminal_status

    assert repository.size() == 0
    assert store.size() == 0