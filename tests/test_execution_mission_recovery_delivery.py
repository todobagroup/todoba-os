"""
TODOBA Proof060

Execution Mission Recovery Delivery Test

Proves:

Persisted Mission
        ↓
Recovery
        ↓
Delivery Bridge
        ↓
Recovered Mission delivered
"""
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)

from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from pathlib import Path

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)

from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)

from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)

from backend.trading.execution.execution_mission_recovery import (
    ExecutionMissionRecovery,
)

def test_execution_mission_recovery_delivery(
    tmp_path: Path,
):

    mission = ExecutionMission(
        mission_id="proof060-001",
        agent_id="agent-001",
        account_fingerprint="account-test",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=4050.0,
        sl=4040.0,
        tp=4070.0,
        magic_number=10001,
        comment="proof060",
        created_at="2026-08-05T00:00:00Z",
        expires_at=None,
        sequence=1,
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

    restored_repository = ExecutionMissionRepository()

    store = ExecutionMissionStore()

    delivery_bridge = ExecutionMissionDeliveryBridge(
    store
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

    assert recovered.mission_id == (
        "proof060-001"
    )

    assert recovered.agent_id == (
        "agent-001"
    )