from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


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
    order = 123456
    deal = 0
    volume = 0.01
    price = 4100.0
    comment = "done"


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



class DummyProfile:
    pass



def test_live_execution_pipeline_mt5_boundary():

    fake_mt5 = FakeMT5()


    pipeline = LiveExecutionPipeline(
        profile=DummyProfile(),
        symbol_map={
            "XAUUSD": "XAUUSD",
        },
        mt5_module=fake_mt5,
    )


    plan = type(
        "ExecutionPlan",
        (),
        {
            "symbol": "XAUUSD",
            "order_type": "BUY LIMIT",
            "entry": 4090.0,
            "sl": 4000.0,
            "tp": 4200.0,
            "comment": "TODOBA Proof011",
        },
    )()


    result = pipeline.execute(
        plan
    )


    assert result is not None


    assert fake_mt5.request is not None


    assert fake_mt5.request["symbol"] == (
        "XAUUSD"
    )


    assert fake_mt5.request["action"] == (
        fake_mt5.TRADE_ACTION_PENDING
    )