from datetime import datetime, timezone

from backend.brain.memory import MemoryEngine

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

from backend.trading.lifecycle.trade_memory_bridge import (
    TradeMemoryBridge,
)

from backend.trading.lifecycle.trade_record_builder import (
    TradeRecordBuilder,
)

from backend.trading.lifecycle.trade_reflection_pipeline import (
    TradeReflectionPipeline,
)

from backend.trading.models.order_result import (
    OrderResult,
)


class FakeDeal:

    ticket = 400001
    order = 100001

    symbol = "XAUUSD"
    type = 1
    entry = 1

    volume = 0.01
    price = 4050.0

    time = 1785801600

    profit = 10.0
    commission = 0.0
    swap = 0.0
    fee = 0.0

    reason = 0

    comment = "proof058"


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


def test_full_trade_lifecycle_end_to_end():
    order_result = OrderResult(
        success=True,
        order=100001,
        deal=400001,
        volume=0.01,
        price=4050.0,
        retcode=10009,
        comment="executed",
)

    trade_record = TradeRecordBuilder().build(
        trade_id="proof058-001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        order_result=order_result,
    )

    registry = OpenTradeRegistry()

    registry.register(
        trade_record=trade_record,
        position_id=300001,
    )

    memory = MemoryEngine()

    reflection_pipeline = TradeReflectionPipeline(
        memory_bridge=TradeMemoryBridge(
            memory
        ),
    )

    monitor = TradeLifecycleMonitor(
        registry=registry,
        history_reader=MT5TradeHistoryReader(
            FakeMT5()
        ),
        reflection_pipeline=reflection_pipeline,
        mt5_module=FakeMT5(),
    )

    result = monitor.check_trade(
        "proof058-001"
    )

    assert result.status == (
        "reflected"
    )

    assert result.trade_id == (
        "proof058-001"
    )

    experiences = memory.list()

    assert len(experiences) == 1

    assert "trade_outcome" in (
        experiences[0].content
    )