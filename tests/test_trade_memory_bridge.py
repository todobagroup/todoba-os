"""
Tests for TODOBA TradeMemoryBridge.
"""

import json

import pytest

from backend.brain.memory import MemoryEngine
from backend.trading.lifecycle.trade_experience import (
    TradeExperience,
)
from backend.trading.lifecycle.trade_memory_bridge import (
    TradeMemoryBridge,
)
from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)
from backend.trading.lifecycle.trade_status import (
    TradeStatus,
)


def test_open_trade_becomes_brain_experience():
    memory = MemoryEngine()
    bridge = TradeMemoryBridge(memory)

    trade_record = TradeRecord(
        trade_id="TRD-000001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.OPEN,
        order=10001,
        deal=20001,
    )

    experience = bridge.remember_open_trade(
        trade_record,
        origin="telegram",
        context={
            "chat_id": -100123,
            "message_id": 500,
        },
    )

    saved = memory.get(
        experience.experience_id
    )

    assert saved == experience
    assert experience.source == "trading"

    content = json.loads(
        experience.content
    )

    assert content["event"] == "trade_opened"
    assert content["trade_id"] == "TRD-000001"
    assert content["origin"] == "telegram"
    assert content["symbol"] == "XAUUSD"
    assert content["status"] == "open"
    assert content["order"] == 10001
    assert content["deal"] == 20001

    assert (
        content["context"]["message_id"]
        == 500
    )


def test_trade_outcome_becomes_brain_experience():
    memory = MemoryEngine()
    bridge = TradeMemoryBridge(memory)

    trade_experience = TradeExperience(
        trade_id="TRD-000001",
        outcome="profit",
        reason="Take profit reached.",
    )

    experience = bridge.remember_trade_outcome(
        trade_experience,
        context={
            "profit": 50.0,
            "close_reason": "take_profit",
        },
    )

    saved = memory.get(
        experience.experience_id
    )

    assert saved == experience

    content = json.loads(
        experience.content
    )

    assert content["event"] == "trade_outcome"
    assert content["trade_id"] == "TRD-000001"
    assert content["outcome"] == "profit"

    assert (
        content["reason"]
        == "Take profit reached."
    )

    assert content["context"]["profit"] == 50.0


def test_memory_preserves_multiple_trade_events():
    memory = MemoryEngine()
    bridge = TradeMemoryBridge(memory)

    trade_record = TradeRecord(
        trade_id="TRD-000002",
        symbol="XAUUSD",
        action="SELL",
        volume=0.01,
        status=TradeStatus.OPEN,
        order=10002,
        deal=20002,
    )

    trade_experience = TradeExperience(
        trade_id="TRD-000002",
        outcome="loss",
        reason="Stop loss reached.",
    )

    bridge.remember_open_trade(
        trade_record
    )

    bridge.remember_trade_outcome(
        trade_experience
    )

    assert len(memory.list()) == 2


def test_bridge_rejects_invalid_open_trade():
    memory = MemoryEngine()
    bridge = TradeMemoryBridge(memory)

    with pytest.raises(
        TypeError,
        match="requires TradeRecord",
    ):
        bridge.remember_open_trade(
            "not-a-trade-record"
        )


def test_bridge_rejects_invalid_outcome():
    memory = MemoryEngine()
    bridge = TradeMemoryBridge(memory)

    with pytest.raises(
        TypeError,
        match="requires TradeExperience",
    ):
        bridge.remember_trade_outcome(
            "not-a-trade-experience"
        )