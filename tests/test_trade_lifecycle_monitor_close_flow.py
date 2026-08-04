from datetime import datetime, timezone

from backend.trading.lifecycle.closed_trade_observation import (
    ClosedTradeObservation,
)

from backend.trading.lifecycle.mt5_trade_history_reader import (
    MT5TradeHistoryReader,
)

from backend.trading.lifecycle.open_trade_registry import (
    OpenTradeRegistry,
)

from backend.trading.lifecycle.trade_lifecycle_monitor import (
    TradeLifecycleMonitor,
)

from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)

from backend.trading.lifecycle.trade_status import (
    TradeStatus,
)


class FakeDeal:

    ticket = 900001
    order = 800001
    symbol = "XAUUSD"

    type = 1
    entry = 1

    volume = 0.01
    price = 4040.5

    time = 1785801600

    profit = 10.0
    commission = 0.0
    swap = 0.0
    fee = 0.0

    reason = 0

    comment = "closed"


class FakeMT5:

    DEAL_ENTRY_OUT = 1
    DEAL_ENTRY_OUT_BY = 2
    DEAL_ENTRY_INOUT = 3

    DEAL_TYPE_SELL = 1
    DEAL_TYPE_BUY = 0

    DEAL_REASON_TP = 0
    DEAL_REASON_SL = 1
    DEAL_REASON_SO = 2
    DEAL_REASON_CLIENT = 3
    DEAL_REASON_MOBILE = 4
    DEAL_REASON_WEB = 5
    DEAL_REASON_EXPERT = 6

    def positions_get(
        self,
        ticket,
    ):
        return []

    def history_deals_get(
        self,
        position,
    ):
        return [
            FakeDeal()
        ]

    def last_error(self):
        return (
            0,
            "OK",
        )


from backend.trading.lifecycle.trade_reflection_pipeline import (
    TradeReflectionPipeline,
)


class FakeReflectionPipeline(
    TradeReflectionPipeline
):

    def __init__(self):
        pass

    def reflect(
        self,
        *,
        trade_record,
        observation,
        context,
    ):
        return "reflected"

def test_trade_lifecycle_monitor_detects_closed_position():

    trade_record = TradeRecord(
        trade_id="proof056-001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.OPEN,
        order=800001,
        deal=900001,
    )

    registry = OpenTradeRegistry()

    registry.register(
        trade_record=trade_record,
        position_id=700001,
    )

    history_reader = MT5TradeHistoryReader(
        FakeMT5()
    )

    monitor = TradeLifecycleMonitor(
        registry=registry,
        history_reader=history_reader,
        reflection_pipeline=FakeReflectionPipeline(),
        mt5_module=FakeMT5(),
    )

    result = monitor.check_trade(
        "proof056-001"
    )

    assert result.status == (
        "reflected"
    )

    assert result.trade_id == (
        "proof056-001"
    )

    assert result.position_id == (
        700001
    )

    assert result.reflection == (
        "reflected"
    )

    assert registry.get(
        "proof056-001"
    ) is None