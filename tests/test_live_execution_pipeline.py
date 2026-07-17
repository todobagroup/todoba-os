import sys
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import pytest

from backend.trading.execution.execution_plan import (
    ExecutionPlan,
)
from backend.trading.execution.live_execution_pipeline import (
    LiveExecutionPipeline,
)
from backend.trading.pending.pending_order_record import (
    PendingOrderRecord,
)


class FakeMT5:

    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TYPE_BUY_STOP = 4
    ORDER_TYPE_SELL_STOP = 5

    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5

    ORDER_TIME_GTC = 0

    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2

    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008

    def __init__(self):
        self.selected_symbol = None
        self.sent_request = None

    def symbol_select(
        self,
        symbol,
        enabled,
    ):
        self.selected_symbol = (
            symbol,
            enabled,
        )
        return True

    def symbol_info(
        self,
        symbol,
    ):
        return SimpleNamespace(
            digits=2,
            point=0.01,
            trade_stops_level=10,
        )

    def symbol_info_tick(
        self,
        symbol,
    ):
        return SimpleNamespace(
            ask=3300.00,
            bid=3299.80,
        )

    def account_info(self):
        return SimpleNamespace(
            equity=10000.0,
        )

    def order_send(
        self,
        request,
    ):
        self.sent_request = request

        return SimpleNamespace(
            retcode=self.TRADE_RETCODE_PLACED,
            order=70001,
            deal=0,
            volume=request["volume"],
            price=request["price"],
            comment="Request accepted",
        )


def create_pending_plan():

    return ExecutionPlan(
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        entry=3290.0,
        sl=3280.0,
        tp=3310.0,
        lot=None,
        magic_number=10001,
        comment="TODOBA:test_pending",
    )


def test_pipeline_uses_injected_mt5_module():

    fake_mt5 = FakeMT5()

    pipeline = LiveExecutionPipeline(
        profile=object(),
        symbol_map={
            "XAUUSD": "XAUUSD.a",
        },
        mt5_module=fake_mt5,
    )

    result = pipeline.execute(
        create_pending_plan()
    )

    assert isinstance(
        result,
        PendingOrderRecord,
    )

    assert fake_mt5.selected_symbol == (
        "XAUUSD.a",
        True,
    )

    assert fake_mt5.sent_request is not None

    assert (
        fake_mt5.sent_request["symbol"]
        == "XAUUSD.a"
    )

    assert (
        fake_mt5.sent_request["action"]
        == fake_mt5.TRADE_ACTION_PENDING
    )

    assert (
        fake_mt5.sent_request["type"]
        == fake_mt5.ORDER_TYPE_BUY_LIMIT
    )

    assert result.order == 70001


def test_pending_order_requires_entry_price():

    fake_mt5 = FakeMT5()

    pipeline = LiveExecutionPipeline(
        profile=object(),
        symbol_map={
            "XAUUSD": "XAUUSD.a",
        },
        mt5_module=fake_mt5,
    )

    plan = ExecutionPlan(
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        entry=None,
        sl=3280.0,
        tp=3310.0,
        lot=None,
        magic_number=10001,
        comment="TODOBA:test_missing_entry",
    )

    with pytest.raises(
        ValueError,
        match="requires an entry price",
    ):
        pipeline.execute(plan)

    assert fake_mt5.sent_request is None