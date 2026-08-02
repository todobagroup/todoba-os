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

from backend.trading.execution.live_execution_pipeline import (
    LiveExecutionPipeline,
)


class FakeSymbolInfo:

    digits = 2
    point = 0.01
    trade_stops_level = 10


class FakeTick:

    ask = 4100.0
    bid = 4099.0


class FakeAccountInfo:

    equity = 10000.0


class FakeOrderResult:

    retcode = 10009
    order = 999001
    deal = 0
    volume = 0.01
    price = 4090.0
    comment = "TODOBA Proof013"


class FakeMT5:

    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1

    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TYPE_BUY_STOP = 4
    ORDER_TYPE_SELL_STOP = 5

    TRADE_ACTION_DEAL = 10
    TRADE_ACTION_PENDING = 11

    ORDER_TIME_GTC = 20

    ORDER_FILLING_RETURN = 30
    ORDER_FILLING_IOC = 31

    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008


    def symbol_select(
        self,
        symbol,
        enabled,
    ):
        return True


    def symbol_info(
        self,
        symbol,
    ):
        return FakeSymbolInfo()


    def symbol_info_tick(
        self,
        symbol,
    ):
        return FakeTick()


    def account_info(
        self,
    ):
        return FakeAccountInfo()


    def order_send(
        self,
        request,
    ):
        self.request = request

        return FakeOrderResult()



class DummyExecutionPipeline:

    def __init__(self):

        self.pipeline = LiveExecutionPipeline(
            profile=None,
            symbol_map={
                "XAUUSD": "XAUUSD",
            },
            mt5_module=FakeMT5(),
        )


    def execute(
        self,
        plan,
    ):

        return self.pipeline.execute(
            plan
        )


class DummyMT5:
    pass


def create_memory():

    return MemoryEngine.__new__(
        MemoryEngine
    )



def test_execution_mission_full_mt5_boundary_flow(
    tmp_path,
):

    pipeline = DummyExecutionPipeline()


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
        mission_id="full-mt5-flow-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4090.0,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Full MT5 Flow",
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


    assert result is not None


    assert result.order_type == (
        "BUY LIMIT"
    )


    assert store.size() == 0