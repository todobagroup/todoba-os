from datetime import datetime, timezone

from backend.brain.memory import MemoryEngine

from backend.trading.lifecycle.closed_trade_observation import (
    ClosedTradeObservation,
)

from backend.trading.lifecycle.trade_memory_bridge import (
    TradeMemoryBridge,
)

from backend.trading.lifecycle.trade_reflection_pipeline import (
    TradeReflectionPipeline,
)

from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)

from backend.trading.lifecycle.trade_status import (
    TradeStatus,
)


def test_closed_trade_reflection_creates_memory_experience():

    memory = MemoryEngine()

    memory_bridge = TradeMemoryBridge(
        memory
    )

    pipeline = TradeReflectionPipeline(
        memory_bridge=memory_bridge,
    )

    trade_record = TradeRecord(
        trade_id="proof057-001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.CLOSED,
        order=100001,
        deal=200001,
    )

    observation = ClosedTradeObservation(
        position_id=300001,
        close_deal_id=400001,
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        close_price=4050.0,
        closed_at=datetime.now(
            timezone.utc
        ),
        gross_profit=10.0,
        commission=0.0,
        swap=0.0,
        fee=0.0,
        net_profit=10.0,
        close_reason="take_profit",
        order_id=100001,
        comment="proof057",
    )

    result = pipeline.reflect(
        trade_record=trade_record,
        observation=observation,
    )

    assert result.evaluation.outcome == (
        "profit"
    )

    assert result.trade_experience.trade_id == (
        "proof057-001"
    )

    assert result.memory_experience.source == (
        "trading"
    )

    experiences = memory.list()

    assert len(experiences) == 1

    assert "trade_outcome" in (
        experiences[0].content
    )