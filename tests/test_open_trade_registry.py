"""
Tests for TODOBA OpenTradeRegistry.
"""

import pytest

from backend.trading.lifecycle.open_trade_registry import (
    OpenTradeRegistry,
)
from backend.trading.lifecycle.trade_record import TradeRecord
from backend.trading.lifecycle.trade_status import TradeStatus


def create_open_trade() -> TradeRecord:
    return TradeRecord(
        trade_id="TRD-000001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.OPEN,
        order=80001,
        deal=70001,
    )


def test_open_trade_can_be_registered():
    registry = OpenTradeRegistry()

    tracked = registry.register(
        trade_record=create_open_trade(),
        position_id=90001,
        context={
            "origin": "telegram",
            "message_id": 500,
        },
    )

    assert tracked.position_id == 90001
    assert registry.size() == 1

    saved = registry.get(
        "TRD-000001"
    )

    assert saved == tracked
    assert saved.context["origin"] == "telegram"


def test_registered_trade_can_be_removed():
    registry = OpenTradeRegistry()

    registry.register(
        trade_record=create_open_trade(),
        position_id=90001,
    )

    removed = registry.remove(
        "TRD-000001"
    )

    assert removed is not None
    assert registry.size() == 0


def test_closed_trade_cannot_be_registered():
    registry = OpenTradeRegistry()

    trade = create_open_trade()
    trade.status = TradeStatus.CLOSED

    with pytest.raises(
        ValueError,
        match="Only OPEN",
    ):
        registry.register(
            trade_record=trade,
            position_id=90001,
        )


def test_duplicate_trade_is_rejected():
    registry = OpenTradeRegistry()
    trade = create_open_trade()

    registry.register(
        trade_record=trade,
        position_id=90001,
    )

    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        registry.register(
            trade_record=trade,
            position_id=90001,
        )


def test_invalid_position_id_is_rejected():
    registry = OpenTradeRegistry()

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        registry.register(
            trade_record=create_open_trade(),
            position_id=0,
        )