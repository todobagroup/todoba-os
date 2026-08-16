"""
TODOBA Control Mission Recovery Delivery Tests

Proves that recovery:

- restores valid persisted control missions
- repairs CREATED missions through lifecycle ownership
- redelivers QUEUED and orphaned DELIVERED missions
- preserves active delivery lease ownership
- rejects missions without lifecycle ownership
- never redelivers acknowledged, executing, or terminal missions
- removes terminal FAILED and COMPLETED missions
"""

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
from backend.trading.control.control_mission_delivery_lease import (
    ControlMissionDeliveryLease,
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
from backend.trading.control.control_mission_recovery import (
    ControlMissionRecovery,
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
from backend.trading.control.control_mission_store import (
    ControlMissionStore,
)


def build_mission(
    mission_id: str,
) -> ControlMission:
    return ControlMission(
        mission_id=mission_id,
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        action=ControlAction.CLOSE_GREEN,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=5414928751,
        created_at="2026-08-15T00:00:00Z",
        expires_at="2026-08-15T01:00:00Z",
        sequence=1,
    )


def persist_mission(
    *,
    tmp_path: Path,
    mission: ControlMission,
) -> ControlMissionPersistence:
    repository = ControlMissionRepository()

    repository.save(
        mission
    )

    persistence = ControlMissionPersistence(
        tmp_path / "control_missions.json"
    )

    persistence.save(
        repository
    )

    return persistence


def build_recovery(
    *,
    persistence: ControlMissionPersistence,
    registry: ControlMissionRegistry | None = None,
    lifecycle_service: (
        ControlMissionLifecycleService | None
    ) = None,
    lease_registry: (
        ControlMissionDeliveryLeaseRegistry | None
    ) = None,
) -> tuple[
    ControlMissionRecovery,
    ControlMissionRepository,
    ControlMissionStore,
]:
    repository = ControlMissionRepository()
    store = ControlMissionStore()

    recovery = ControlMissionRecovery(
        repository=repository,
        persistence=persistence,
        delivery_bridge=(
            ControlMissionDeliveryBridge(
                store
            )
        ),
        registry=registry,
        lifecycle_service=lifecycle_service,
        lease_registry=lease_registry,
    )

    return recovery, repository, store


def test_control_mission_recovery_delivery(
    tmp_path: Path,
) -> None:
    mission = build_mission(
        "control-recovery-001"
    )

    persistence = persist_mission(
        tmp_path=tmp_path,
        mission=mission,
    )

    recovery, _, store = build_recovery(
        persistence=persistence
    )

    restored_count = recovery.restore()

    assert restored_count == 1
    assert store.size() == 1

    recovered = store.pop()

    assert recovered is not None
    assert recovered.mission_id == (
        mission.mission_id
    )
    assert recovered.agent_id == (
        mission.agent_id
    )


def test_created_mission_is_queued_before_recovery_delivery(
    tmp_path: Path,
) -> None:
    mission = build_mission(
        "control-created-recovery-001"
    )

    persistence = persist_mission(
        tmp_path=tmp_path,
        mission=mission,
    )

    registry = ControlMissionRegistry()

    registry.register(
        ControlMissionRecord(
            mission=mission
        )
    )

    lifecycle_service = (
        ControlMissionLifecycleService(
            registry
        )
    )

    recovery, _, store = build_recovery(
        persistence=persistence,
        registry=registry,
        lifecycle_service=lifecycle_service,
    )

    assert recovery.restore() == 1
    assert store.size() == 1

    record = registry.get(
        mission.mission_id
    )

    assert record is not None
    assert record.status is (
        ControlMissionStatus.QUEUED
    )


def test_queued_mission_without_lease_is_redelivered(
    tmp_path: Path,
) -> None:
    mission = build_mission(
        "control-queued-recovery-001"
    )

    persistence = persist_mission(
        tmp_path=tmp_path,
        mission=mission,
    )

    registry = ControlMissionRegistry()

    registry.register(
        ControlMissionRecord(
            mission=mission,
            status=ControlMissionStatus.QUEUED,
        )
    )

    recovery, _, store = build_recovery(
        persistence=persistence,
        registry=registry,
    )

    assert recovery.restore() == 1
    assert store.size() == 1


def test_active_delivery_lease_prevents_restart_redelivery(
    tmp_path: Path,
) -> None:
    mission = build_mission(
        "control-leased-recovery-001"
    )

    persistence = persist_mission(
        tmp_path=tmp_path,
        mission=mission,
    )

    registry = ControlMissionRegistry()

    registry.register(
        ControlMissionRecord(
            mission=mission,
            status=ControlMissionStatus.QUEUED,
        )
    )

    lease_registry = (
        ControlMissionDeliveryLeaseRegistry()
    )

    lease_registry.acquire(
        ControlMissionDeliveryLease(
            mission_id=mission.mission_id,
            agent_id=mission.agent_id,
            leased_at="2026-08-15T00:00:10Z",
            expires_at="2026-08-15T00:00:40Z",
        )
    )

    recovery, repository, store = build_recovery(
        persistence=persistence,
        registry=registry,
        lease_registry=lease_registry,
    )

    assert recovery.restore() == 0
    assert store.size() == 0
    assert repository.get(
        mission.mission_id
    ) == mission


def test_delivered_mission_without_lease_is_redelivered(
    tmp_path: Path,
) -> None:
    mission = build_mission(
        "control-delivered-recovery-001"
    )

    persistence = persist_mission(
        tmp_path=tmp_path,
        mission=mission,
    )

    registry = ControlMissionRegistry()

    registry.register(
        ControlMissionRecord(
            mission=mission,
            status=ControlMissionStatus.DELIVERED,
            delivery_attempt_count=1,
        )
    )

    recovery, _, store = build_recovery(
        persistence=persistence,
        registry=registry,
        lease_registry=(
            ControlMissionDeliveryLeaseRegistry()
        ),
    )

    assert recovery.restore() == 1
    assert store.size() == 1


@pytest.mark.parametrize(
    "in_flight_status",
    [
        ControlMissionStatus.ACKNOWLEDGED,
        ControlMissionStatus.EXECUTING,
    ],
)
def test_acknowledged_or_executing_mission_is_not_redelivered(
    tmp_path: Path,
    in_flight_status: ControlMissionStatus,
) -> None:
    mission = build_mission(
        f"control-in-flight-{in_flight_status.value}"
    )

    persistence = persist_mission(
        tmp_path=tmp_path,
        mission=mission,
    )

    registry = ControlMissionRegistry()

    registry.register(
        ControlMissionRecord(
            mission=mission,
            status=in_flight_status,
        )
    )

    recovery, repository, store = build_recovery(
        persistence=persistence,
        registry=registry,
    )

    assert recovery.restore() == 0
    assert store.size() == 0
    assert repository.get(
        mission.mission_id
    ) == mission


def test_recovery_removes_mission_without_lifecycle_record(
    tmp_path: Path,
) -> None:
    mission = build_mission(
        "control-recovery-orphan-001"
    )

    persistence = persist_mission(
        tmp_path=tmp_path,
        mission=mission,
    )

    recovery, repository, store = build_recovery(
        persistence=persistence,
        registry=ControlMissionRegistry(),
    )

    assert recovery.restore() == 0
    assert store.size() == 0
    assert repository.get(
        mission.mission_id
    ) is None

    persisted_repository = (
        ControlMissionRepository()
    )

    assert persistence.restore(
        persisted_repository
    ) == 0


@pytest.mark.parametrize(
    "terminal_status",
    [
        ControlMissionStatus.FAILED,
        ControlMissionStatus.COMPLETED,
    ],
)
def test_recovery_removes_terminal_mission_without_redelivery(
    tmp_path: Path,
    terminal_status: ControlMissionStatus,
) -> None:
    mission = build_mission(
        f"control-terminal-{terminal_status.value}"
    )

    persistence = persist_mission(
        tmp_path=tmp_path,
        mission=mission,
    )

    registry = ControlMissionRegistry()

    registry.register(
        ControlMissionRecord(
            mission=mission,
            status=terminal_status,
        )
    )

    recovery, repository, store = build_recovery(
        persistence=persistence,
        registry=registry,
    )

    assert recovery.restore() == 0
    assert store.size() == 0
    assert repository.get(
        mission.mission_id
    ) is None

    persisted_repository = (
        ControlMissionRepository()
    )

    assert persistence.restore(
        persisted_repository
    ) == 0