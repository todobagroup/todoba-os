"""
Tests for TODOBA TradeReflectionPipeline.
"""

import json
from datetime import datetime, timezone

import pytest

from backend.brain.memory import MemoryEngine
from backend.trading.lifecycle.closed_trade_observation import (
    ClosedTradeObservation,
)
from backend.trading.lifecycle.trade_memory_bridge import (
    TradeMemoryBridge,
)
from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)
from backend.trading.lifecycle.trade_reflection_pipeline import (
    TradeReflectionPipeline,
)
from backend.trading.lifecycle.trade_status import (
    TradeStatus,
)


def create_observation() -> ClosedTradeObservation:
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


def create_closed_record() -> TradeRecord:
    return TradeRecord(
        trade_id="TRD-000001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.CLOSED,
        order=80001,
        deal=70001,
    )


def test_closed_trade_is_reflected_into_memory():
    memory = MemoryEngine()

    pipeline = TradeReflectionPipeline(
        memory_bridge=TradeMemoryBridge(
            memory
        )
    )

    result = pipeline.reflect(
        trade_record=create_closed_record(),
        observation=create_observation(),
        context={
            "origin": "telegram",
            "message_id": 500,
        },
    )

    assert (
        result.trade_experience.trade_id
        == "TRD-000001"
    )

    assert (
        result.trade_experience.outcome
        == "profit"
    )

    saved = memory.get(
        result.memory_experience.experience_id
    )

    assert saved == result.memory_experience

    content = json.loads(
        result.memory_experience.content
    )

    assert content["event"] == "trade_outcome"
    assert content["trade_id"] == "TRD-000001"
    assert content["outcome"] == "profit"

    assert (
        content["context"]["net_profit"]
        == 19.40
    )

    assert (
        content["context"]["close_reason"]
        == "take_profit"
    )

    assert (
        content["context"]["origin"]
        == "telegram"
    )


def test_open_trade_cannot_be_reflected():
    memory = MemoryEngine()

    pipeline = TradeReflectionPipeline(
        memory_bridge=TradeMemoryBridge(
            memory
        )
    )

    open_record = TradeRecord(
        trade_id="TRD-000002",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.OPEN,
    )

    with pytest.raises(
        ValueError,
        match="must be CLOSED",
    ):
        pipeline.reflect(
            trade_record=open_record,
            observation=create_observation(),
        )

    assert len(memory.list()) == 0


def test_pipeline_rejects_invalid_trade_record():
    memory = MemoryEngine()

    pipeline = TradeReflectionPipeline(
        memory_bridge=TradeMemoryBridge(
            memory
        )
    )

    with pytest.raises(
        TypeError,
        match="requires TradeRecord",
    ):
        pipeline.reflect(
            trade_record="not-a-record",
            observation=create_observation(),
        )
