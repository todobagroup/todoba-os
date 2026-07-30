from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)

from backend.trading.execution.execution_mission_service import (
    ExecutionMissionService,
)

from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)

from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)

from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)

from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)

from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)


def build_mission() -> ExecutionMission:

    return ExecutionMission(
        mission_id="service-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Service Test",
        created_at="2026-07-29T00:00:00Z",
        expires_at="2026-07-30T00:00:00Z",
        sequence=1,
    )


def test_execution_mission_service_creates_and_delivers_mission(
    tmp_path,
):

    repository = ExecutionMissionRepository()

    persistence = ExecutionMissionPersistence(
        tmp_path / "execution_missions.json"
    )

    store = ExecutionMissionStore()

    bridge = ExecutionMissionDeliveryBridge(
        store
    )

    registry = ExecutionMissionRegistry()

    service = ExecutionMissionService(
        repository,
        persistence,
        bridge,
        registry,
    )

    mission = build_mission()

    result = service.create_mission(
        mission
    )

    assert result == mission

    assert repository.size() == 1

    assert registry.size() == 1

    assert store.size() == 1

    delivered = store.pop()

    assert delivered is not None

    assert delivered.mission_id == (
        "service-001"
    )