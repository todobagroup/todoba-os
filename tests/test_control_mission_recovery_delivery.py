"""
TODOBA Control Mission Recovery Delivery Tests

Proves that recovery:

- restores valid persisted control missions
- rejects missions without lifecycle ownership
- removes terminal FAILED and COMPLETED missions
- never redelivers terminal control missions
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
        expires_at="2026-08-15T00:01:00Z",
        sequence=1,
    )


def build_recovery(
    *,
    persistence: ControlMissionPersistence,
    registry: ControlMissionRegistry | None = None,
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
    )

    return recovery, repository, store


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

    restored_count = recovery.restore()

    assert restored_count == 0
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

    restored_count = recovery.restore()

    assert restored_count == 0
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