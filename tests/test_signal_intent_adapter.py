"""
Tests for TODOBA SignalIntentAdapter.
"""

import pytest

from backend.trading.intent.signal_intent_adapter import (
    SignalIntentAdapter,
)
from backend.trading.models.signal import Signal


def test_buy_now_signal_becomes_buy_intent():
    signal = Signal(
        order_type="BUY NOW",
        symbol="XAUUSD",
        entry=None,
        sl=4095.0,
        tp=4125.0,
    )

    intent = SignalIntentAdapter().to_intent(
        signal
    )

    assert intent.action == "BUY"
    assert intent.asset == "XAUUSD"
    assert intent.entry is None
    assert intent.sl == 4095.0
    assert intent.tp == 4125.0


def test_sell_now_signal_becomes_sell_intent():
    signal = Signal(
        order_type="SELL NOW",
        symbol="XAUUSD",
        entry=None,
        sl=4125.0,
        tp=4095.0,
    )

    intent = SignalIntentAdapter().to_intent(
        signal
    )

    assert intent.action == "SELL"
    assert intent.asset == "XAUUSD"


def test_adapter_rejects_invalid_input():
    adapter = SignalIntentAdapter()

    with pytest.raises(
        TypeError,
        match="requires Signal",
    ):
        adapter.to_intent(
            "not-a-signal"
        )