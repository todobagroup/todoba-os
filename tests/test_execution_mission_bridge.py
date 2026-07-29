"""
TODOBA Execution Mission Bridge Tests

Proof:

ExecutionMission
        ->
ExecutionMissionBridge
        ->
TradingDepartment
        ->
TradingRuntime
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.brain.memory import MemoryEngine
from backend.task.task import Task
from backend.trading.department.trading_department import (
    TradingDepartment,
)
from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_bridge import (
    ExecutionMissionBridge,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)


class DummyExecutionPipeline:
    def execute(self, plan):
        return "execution-success"


class DummyMT5:
    pass


def create_memory() -> MemoryEngine:
    return MemoryEngine.__new__(
        MemoryEngine
    )


def test_execution_mission_bridge_dispatches_mission(
    tmp_path,
):

    department = TradingDepartment(
        execution_pipeline=(
            DummyExecutionPipeline()
        ),
        open_trades_storage_path=(
            tmp_path / "open_trades.json"
        ),
        memory=create_memory(),
        mt5_module=DummyMT5(),
    )

    department.runtime.start()

    store = ExecutionMissionStore()

    store.push(
        ExecutionMission(
            mission_id="bridge-proof-001",
            agent_id="trusted-agent-001",
            account_fingerprint="account-test",
            symbol="XAUUSD",
            order_type="BUY LIMIT",
            volume=0.01,
            entry=4100.0,
            sl=4090.0,
            tp=4120.0,
            magic_number=10001,
            comment="TODOBA",
            created_at="2026-07-29T00:00:00",
            expires_at="2026-07-29T01:00:00",
            sequence=1,
        )
    )

    bridge = ExecutionMissionBridge(
        store=store,
        department=department,
    )

    result = bridge.dispatch_next()

    assert result == "execution-success"

    assert store.size() == 0