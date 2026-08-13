"""
TODOBA Trade Task Remote Execution Bridge Tests

Proof:
Approved trade Task
->
TradeTaskExecutionMissionAdapter
->
ExecutionMissionService
->
existing delivery queue
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.task.task_factory import TaskFactory
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)
from backend.trading.execution.execution_mission_record_persistence import (
    ExecutionMissionRecordPersistence,
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
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)
from backend.trading.execution.trade_task_remote_execution_bridge import (
    TradeTaskRemoteExecutionBridge,
)
from backend.trading.intent.trading_intent import (
    TradingIntent,
)


def test_trade_task_is_delivered_as_execution_mission(
    tmp_path,
):
    repository = ExecutionMissionRepository()

    persistence = ExecutionMissionPersistence(
        tmp_path / "execution_missions.json"
    )

    store = ExecutionMissionStore()

    delivery_bridge = ExecutionMissionDeliveryBridge(
        store
    )

    registry = ExecutionMissionRegistry()

    record_persistence = (
        ExecutionMissionRecordPersistence(
            tmp_path / "execution_mission_records.json"
        )
    )

    service = ExecutionMissionService(
        repository,
        persistence,
        delivery_bridge,
        registry,
        record_persistence,
    )

    bridge = TradeTaskRemoteExecutionBridge(
        mission_service=service,
    )

    intent = TradingIntent(
        order_type="SELL NOW",
        asset="XAUUSD",
        sl=4334.0,
        tp=4303.0,
    )

    task = TaskFactory.create(
        task_type="trade",
        payload=intent,
    )

    mission = bridge.dispatch(
        task,
        mission_id="proof087-remote-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        volume=0.01,
        magic_number=10001,
        comment="TODOBA proof087 remote",
        created_at="2026-08-10T00:00:00Z",
        expires_at="2026-08-10T00:02:00Z",
        sequence=87,
    )

    assert mission.mission_id == (
        "proof087-remote-001"
    )

    assert repository.size() == 1
    assert registry.size() == 1
    assert store.size() == 1

    queued = store.pop()

    assert queued is not None
    assert queued.mission_id == (
        "proof087-remote-001"
    )
    assert queued.order_type == "SELL NOW"
    assert queued.symbol == "XAUUSD"
    assert queued.sl == 4334.0
    assert queued.tp == 4303.0