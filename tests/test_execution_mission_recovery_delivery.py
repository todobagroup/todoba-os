"""
TODOBA Execution Mission Recovery Delivery Tests

Proves:

Persisted Mission
↓
Recovery
↓
Delivery Bridge
↓
Recovered Mission delivered

Also proves:

Persisted Mission
+
Missing Lifecycle Record
↓
Recovery
↓
Mission must not be delivered
"""

from pathlib import Path

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
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


def test_execution_mission_recovery_delivery(
    tmp_path: Path,
) -> None:
    mission = build_mission(
        "proof060-001"
    )

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

    restored_repository = (
        ExecutionMissionRepository()
    )

    store = ExecutionMissionStore()

    delivery_bridge = (
        ExecutionMissionDeliveryBridge(
            store
        )
    )

    recovery = ExecutionMissionRecovery(
        repository=restored_repository,
        persistence=persistence,
        delivery_bridge=delivery_bridge,
    )

    restored = recovery.restore()

    assert restored == 1

    assert store.size() == 1

    recovered = store.pop()

    assert recovered is not None

    assert recovered.mission_id == (
        "proof060-001"
    )

    assert recovered.agent_id == (
        "agent-001"
    )


def test_recovery_does_not_deliver_mission_without_lifecycle_record(
    tmp_path: Path,
) -> None:
    mission = build_mission(
        "recovery-orphan-001"
    )

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

    restored_repository = (
        ExecutionMissionRepository()
    )

    registry = ExecutionMissionRegistry()

    store = ExecutionMissionStore()

    delivery_bridge = (
        ExecutionMissionDeliveryBridge(
            store
        )
    )

    recovery = ExecutionMissionRecovery(
        repository=restored_repository,
        persistence=persistence,
        delivery_bridge=delivery_bridge,
        registry=registry,
    )

    restored = recovery.restore()

    assert restored == 0

    assert store.size() == 0