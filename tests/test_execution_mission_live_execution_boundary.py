from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from backend.brain.memory import MemoryEngine

from backend.trading.department.trading_department import (
    TradingDepartment,
)

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)

from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)

from backend.trading.execution.execution_mission_bridge import (
    ExecutionMissionBridge,
)


class DummyExecutionPipeline:

    def __init__(self):

        self.received_plan = None


    def execute(
        self,
        plan,
    ):

        self.received_plan = plan

        return "pipeline-success"


class DummyMT5:
    pass


def create_memory():

    return MemoryEngine.__new__(
        MemoryEngine
    )


def test_execution_mission_live_execution_boundary(
    tmp_path,
):

    pipeline = (
        DummyExecutionPipeline()
    )


    department = TradingDepartment(
        execution_pipeline=pipeline,
        open_trades_storage_path=(
            tmp_path / "open_trades.json"
        ),
        memory=create_memory(),
        mt5_module=DummyMT5(),
    )


    department.runtime.start()


    store = ExecutionMissionStore()


    mission = ExecutionMission(
        mission_id="live-boundary-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Live Boundary",
        created_at="2026-08-02T00:00:00Z",
        expires_at="2026-08-03T00:00:00Z",
        sequence=1,
    )


    store.push(
        mission
    )


    bridge = ExecutionMissionBridge(
        store=store,
        department=department,
    )


    result = bridge.dispatch_next()


    assert result == (
        "pipeline-success"
    )


    assert pipeline.received_plan is not None


    assert pipeline.received_plan.symbol == (
        "XAUUSD"
    )


    assert pipeline.received_plan.order_type == (
        "BUY LIMIT"
    )


    assert store.size() == 0