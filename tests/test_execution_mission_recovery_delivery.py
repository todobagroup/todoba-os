"""
TODOBA Execution Mission Recovery Delivery Tests

Proves that recovery:

- restores valid persisted missions
- rejects missions without lifecycle ownership
- removes terminal FAILED and COMPLETED missions
- never redelivers terminal missions
"""

from pathlib import Path

import pytest

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_recovery import (
    ExecutionMissionRecovery,
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
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)


def build_mission(
    mission_id: str,
) -> ExecutionMission:
    return ExecutionMission(
        mission_id=mission_id,
        agent_id="agent-001",
        account_fingerprint="account-test",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=4050.0,
        sl=4040.0,
        tp=4070.0,
        magic_number=10001,
        comment="recovery-test",
        created_at="2026-08-05T00:00:00Z",
        expires_at=None,
        sequence=1,
    )


def build_recovery(
    *,
    persistence: ExecutionMissionPersistence,
    registry: ExecutionMissionRegistry | None = None,
) -> tuple[
    ExecutionMissionRecovery,
    ExecutionMissionRepository,
    ExecutionMissionStore,
]:
    repository = ExecutionMissionRepository()
    store = ExecutionMissionStore()

    recovery = ExecutionMissionRecovery(
        repository=repository,
        persistence=persistence,
        delivery_bridge=(
            ExecutionMissionDeliveryBridge(
                store
            )
        ),
        registry=registry,
    )

    return recovery, repository, store


def persist_mission(
    *,
    tmp_path: Path,
    mission: ExecutionMission,
) -> ExecutionMissionPersistence:
    repository = ExecutionMissionRepository()

    repository.save(
        mission
    )

    persistence = ExecutionMissionPersistence(
        tmp_path / "missions.json"
    )

    persistence.save(
        repository
    )

    return persistence


def test_execution_mission_recovery_delivery(
    tmp_path: Path,
) -> None:
    mission = build_mission(
        "proof060-001"
    )

    persistence = persist_mission(
        tmp_path=tmp_path,
        mission=mission,
    )

    recovery, _, store = build_recovery(
        persistence=persistence
    )

    restored = recovery.restore()

    assert restored == 1
    assert store.size() == 1

    recovered = store.pop()

    assert recovered is not None
    assert recovered.mission_id == mission.mission_id
    assert recovered.agent_id == mission.agent_id


def test_recovery_removes_mission_without_lifecycle_record(
    tmp_path: Path,
) -> None:
    mission = build_mission(
        "recovery-orphan-001"
    )

    persistence = persist_mission(
        tmp_path=tmp_path,
        mission=mission,
    )

    recovery, repository, store = build_recovery(
        persistence=persistence,
        registry=ExecutionMissionRegistry(),
    )

    restored = recovery.restore()

    assert restored == 0
    assert store.size() == 0
    assert repository.get(
        mission.mission_id
    ) is None

    persisted_repository = (
        ExecutionMissionRepository()
    )

    assert persistence.restore(
        persisted_repository
    ) == 0


@pytest.mark.parametrize(
    "terminal_status",
    [
        ExecutionMissionStatus.FAILED,
        ExecutionMissionStatus.COMPLETED,
    ],
)
def test_recovery_removes_terminal_mission_without_redelivery(
    tmp_path: Path,
    terminal_status: ExecutionMissionStatus,
) -> None:
    mission = build_mission(
        f"terminal-{terminal_status.value}"
    )

    persistence = persist_mission(
        tmp_path=tmp_path,
        mission=mission,
    )

    registry = ExecutionMissionRegistry()

    registry.register(
        ExecutionMissionRecord(
            mission=mission,
            status=terminal_status,
        )
    )

    recovery, repository, store = build_recovery(
        persistence=persistence,
        registry=registry,
    )

    restored = recovery.restore()

    assert restored == 0
    assert store.size() == 0
    assert repository.get(
        mission.mission_id
    ) is None

    persisted_repository = (
        ExecutionMissionRepository()
    )

    assert persistence.restore(
        persisted_repository
    ) == 0