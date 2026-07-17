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

        if (
            request["action"]
            == self.TRADE_ACTION_PENDING
        ):
            retcode = self.TRADE_RETCODE_PLACED
            order = 70001
            deal = 0

        else:
            retcode = self.TRADE_RETCODE_DONE
            order = 70002
            deal = 80001

        return SimpleNamespace(
            retcode=retcode,
            order=order,
            deal=deal,
            volume=request["volume"],
            price=request["price"],
            comment="Request accepted",
        )


def create_pipeline(
    fake_mt5,
):

    return LiveExecutionPipeline(
        profile=object(),
        symbol_map={
            "XAUUSD": "XAUUSD.a",
        },
        mt5_module=fake_mt5,
    )


@pytest.mark.parametrize(
    (
        "order_type",
        "entry",
        "sl",
        "tp",
        "expected_action",
        "expected_mt5_type",
        "expected_price",
        "expected_result_type",
    ),
    [
        (
            "BUY NOW",
            None,
            3290.0,
            3310.0,
            FakeMT5.TRADE_ACTION_DEAL,
            FakeMT5.ORDER_TYPE_BUY,
            3300.00,
            "TradeRecord",
        ),
        (
            "SELL NOW",
            None,
            3310.0,
            3290.0,
            FakeMT5.TRADE_ACTION_DEAL,
            FakeMT5.ORDER_TYPE_SELL,
            3299.80,
            "TradeRecord",
        ),
        (
            "BUY LIMIT",
            3290.0,
            3280.0,
            3310.0,
            FakeMT5.TRADE_ACTION_PENDING,
            FakeMT5.ORDER_TYPE_BUY_LIMIT,
            3290.0,
            "PendingOrderRecord",
        ),
        (
            "SELL LIMIT",
            3310.0,
            3320.0,
            3290.0,
            FakeMT5.TRADE_ACTION_PENDING,
            FakeMT5.ORDER_TYPE_SELL_LIMIT,
            3310.0,
            "PendingOrderRecord",
        ),
        (
            "BUY STOP",
            3310.0,
            3290.0,
            3330.0,
            FakeMT5.TRADE_ACTION_PENDING,
            FakeMT5.ORDER_TYPE_BUY_STOP,
            3310.0,
            "PendingOrderRecord",
        ),
        (
            "SELL STOP",
            3290.0,
            3310.0,
            3270.0,
            FakeMT5.TRADE_ACTION_PENDING,
            FakeMT5.ORDER_TYPE_SELL_STOP,
            3290.0,
            "PendingOrderRecord",
        ),
    ],
)
def test_pipeline_executes_supported_order_types(
    order_type,
    entry,
    sl,
    tp,
    expected_action,
    expected_mt5_type,
    expected_price,
    expected_result_type,
):

    fake_mt5 = FakeMT5()

    pipeline = create_pipeline(
        fake_mt5
    )

    plan = ExecutionPlan(
        symbol="XAUUSD",
        order_type=order_type,
        entry=entry,
        sl=sl,
        tp=tp,
        lot=None,
        magic_number=10001,
        comment=f"TODOBA:test_{order_type}",
    )

    result = pipeline.execute(plan)

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
        == expected_action
    )

    assert (
        fake_mt5.sent_request["type"]
        == expected_mt5_type
    )

    assert (
        fake_mt5.sent_request["price"]
        == expected_price
    )

    assert (
        result.__class__.__name__
        == expected_result_type
    )

    if isinstance(
        result,
        PendingOrderRecord,
    ):
        assert result.order == 70001


@pytest.mark.parametrize(
    "order_type",
    [
        "BUY LIMIT",
        "SELL LIMIT",
        "BUY STOP",
        "SELL STOP",
    ],
)
def test_pending_orders_require_entry_price(
    order_type,
):

    fake_mt5 = FakeMT5()

    pipeline = create_pipeline(
        fake_mt5
    )

    plan = ExecutionPlan(
        symbol="XAUUSD",
        order_type=order_type,
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


@pytest.mark.parametrize(
    (
        "order_type",
        "entry",
        "sl",
        "tp",
        "error_message",
    ),
    [
        (
            "BUY LIMIT",
            3300.00,
            3290.0,
            3310.0,
            "BUY LIMIT entry must be below",
        ),
        (
            "SELL LIMIT",
            3299.80,
            3310.0,
            3290.0,
            "SELL LIMIT entry must be above",
        ),
        (
            "BUY STOP",
            3300.00,
            3290.0,
            3310.0,
            "BUY STOP entry must be above",
        ),
        (
            "SELL STOP",
            3299.80,
            3310.0,
            3290.0,
            "SELL STOP entry must be below",
        ),
    ],
)
def test_pending_orders_reject_entry_on_wrong_market_side(
    order_type,
    entry,
    sl,
    tp,
    error_message,
):

    fake_mt5 = FakeMT5()

    pipeline = create_pipeline(
        fake_mt5
    )

    plan = ExecutionPlan(
        symbol="XAUUSD",
        order_type=order_type,
        entry=entry,
        sl=sl,
        tp=tp,
        lot=None,
        magic_number=10001,
        comment="TODOBA:test_invalid_pending_entry",
    )

    with pytest.raises(
        ValueError,
        match=error_message,
    ):
        pipeline.execute(plan)

    assert fake_mt5.sent_request is None