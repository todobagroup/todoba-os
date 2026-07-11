"""
Tests for TODOBA TradeLifecycleMonitor.

These tests do not connect to MT5.
"""

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
from backend.trading.lifecycle.trade_record import TradeRecord
from backend.trading.lifecycle.trade_reflection_pipeline import (
    TradeReflectionPipeline,
)
from backend.trading.lifecycle.trade_status import TradeStatus


class FakeMT5:
    def __init__(
        self,
        *,
        positions=(),
        fail=False,
    ):
        self.positions = positions
        self.fail = fail
        self.requested_ticket = None

    def positions_get(
        self,
        *,
        ticket,
    ):
        self.requested_ticket = ticket

        if self.fail:
            return None

        return self.positions

    def last_error(self):
        return 500, "positions unavailable"


class FakeHistoryReader(
    MT5TradeHistoryReader
):
    def __init__(
        self,
        observation=None,
    ):
        self.observation = observation
        self.requested_position = None

    def read_closed_position(
        self,
        position_id,
    ):
        self.requested_position = position_id
        return self.observation


def create_trade() -> TradeRecord:
    return TradeRecord(
        trade_id="TRD-000001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.OPEN,
        order=80001,
        deal=70001,
    )


def create_observation():
    return ClosedTradeObservation(
        position_id=90001,
        close_deal_id=70002,
        order_id=80002,
        symbol="GOLD.i#",
        action="BUY",
        volume=0.01,
        close_price=4125.0,
        closed_at=datetime.now(
            timezone.utc
        ),
        gross_profit=20.0,
        commission=-0.50,
        swap=-0.10,
        fee=0.0,
        net_profit=19.40,
        close_reason="take_profit",
        comment="TODOBA",
    )


def create_monitor(
    *,
    positions=(),
    observation=None,
    fail=False,
):
    memory = MemoryEngine()
    registry = OpenTradeRegistry()

    registry.register(
        trade_record=create_trade(),
        position_id=90001,
        context={
            "origin": "telegram",
            "message_id": 500,
        },
    )

    history_reader = FakeHistoryReader(
        observation=observation
    )

    reflection_pipeline = (
        TradeReflectionPipeline(
            memory_bridge=TradeMemoryBridge(
                memory
            )
        )
    )

    monitor = TradeLifecycleMonitor(
        registry=registry,
        history_reader=history_reader,
        reflection_pipeline=(
            reflection_pipeline
        ),
        mt5_module=FakeMT5(
            positions=positions,
            fail=fail,
        ),
    )

    return (
        monitor,
        registry,
        memory,
        history_reader,
    )


def test_open_position_remains_registered():
    monitor, registry, memory, history = (
        create_monitor(
            positions=(object(),)
        )
    )

    result = monitor.check_trade(
        "TRD-000001"
    )

    assert result.status == "open"
    assert registry.size() == 1
    assert len(memory.list()) == 0
    assert history.requested_position is None


def test_closed_position_waits_for_history():
    monitor, registry, memory, history = (
        create_monitor(
            positions=(),
            observation=None,
        )
    )

    result = monitor.check_trade(
        "TRD-000001"
    )

    assert result.status == "awaiting_history"
    assert registry.size() == 1
    assert len(memory.list()) == 0
    assert history.requested_position == 90001


def test_closed_position_is_reflected():
    monitor, registry, memory, history = (
        create_monitor(
            positions=(),
            observation=create_observation(),
        )
    )

    result = monitor.check_trade(
        "TRD-000001"
    )

    assert result.status == "reflected"
    assert result.reflection is not None
    assert registry.size() == 0
    assert len(memory.list()) == 1

    assert (
        result.reflection
        .trade_experience
        .outcome
        == "profit"
    )


def test_mt5_position_failure_is_recorded():
    monitor, registry, memory, _ = (
        create_monitor(
            fail=True
        )
    )

    result = monitor.check_trade(
        "TRD-000001"
    )

    assert result.status == "monitor_failed"
    assert registry.size() == 1
    assert len(memory.list()) == 0

    assert (
        "positions_get failed"
        in result.errors[0]
    )


def test_check_all_processes_registry():
    monitor, registry, _, _ = (
        create_monitor(
            positions=(object(),)
        )
    )

    results = monitor.check_all()

    assert len(results) == 1
    assert results[0].status == "open"
    assert registry.size() == 1