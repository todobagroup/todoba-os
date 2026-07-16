"""
Tests for TODOBA TelegramTaskProducer.

These tests do not connect to Telegram.
These tests do not connect to MT5.
These tests do not send orders.
"""

from datetime import datetime, timezone

from backend.integrations.telegram_task_producer import (
    TelegramTaskProducer,
)
from backend.task.task_status import TaskStatus
from backend.trading.profile.trading_profile import (
    TradingProfile,
)
from backend.trading.signal.incoming_signal import (
    IncomingSignal,
)


def create_profile(
    *,
    max_open_trades: int = 3,
) -> TradingProfile:
    return TradingProfile(
        profile_name="telegram_task_test",
        risk_percent=1.0,
        max_open_trades=max_open_trades,
        allowed_symbols=("XAUUSD",),
        lot_policy_name="FIXED_001",
    )


def create_incoming_signal(
    message: str,
) -> IncomingSignal:
    return IncomingSignal(
        source="telegram",
        message=message,
        received_at=datetime.now(
            timezone.utc
        ),
        sender="demo_channel",
        sender_id=101,
        chat_id=-100123,
        message_id=500,
    )


def test_approved_signal_creates_trade_task():
    producer = TelegramTaskProducer(
        create_profile()
    )

    result = producer.produce(
        create_incoming_signal(
            "BUY GOLD NOW\n"
            "SL 4095\n"
            "TP 4125"
        ),
        open_position_count=0,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    assert result.status == "task_created"
    assert result.task is not None
    assert result.task.task_type == "trade"
    assert result.task.status == TaskStatus.CREATED
    assert result.intent is not None
    assert result.intent.action == "BUY"
    assert result.intent.asset == "XAUUSD"
    assert result.task.payload == result.intent


def test_existing_positions_below_limit_are_allowed():
    producer = TelegramTaskProducer(
        create_profile(
            max_open_trades=3
        )
    )

    result = producer.produce(
        create_incoming_signal(
            "SELL GOLD NOW\n"
            "SL 4125\n"
            "TP 4095"
        ),
        open_position_count=2,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    assert result.status == "task_created"
    assert result.task is not None
    assert result.decision is not None
    assert result.decision.approved is True


def test_position_limit_rejection_creates_no_task():
    producer = TelegramTaskProducer(
        create_profile(
            max_open_trades=3
        )
    )

    result = producer.produce(
        create_incoming_signal(
            "BUY GOLD NOW\n"
            "SL 4095\n"
            "TP 4125"
        ),
        open_position_count=3,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    assert result.status == "decision_rejected"
    assert result.task is None
    assert result.decision is not None
    assert result.decision.approved is False
    assert (
        "Maximum open trade limit reached"
        in result.decision.reason
    )


def test_profile_rejection_creates_no_task():
    profile = TradingProfile(
        profile_name="no_symbols",
        risk_percent=1.0,
        max_open_trades=3,
        allowed_symbols=(),
        lot_policy_name="FIXED_001",
    )

    producer = TelegramTaskProducer(
        profile
    )

    result = producer.produce(
        create_incoming_signal(
            "BUY GOLD NOW\n"
            "SL 4095\n"
            "TP 4125"
        ),
        open_position_count=0,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    assert result.status == "profile_rejected"
    assert result.task is None
    assert "Symbol not allowed." in result.errors


def test_invalid_message_creates_no_task():
    producer = TelegramTaskProducer(
        create_profile()
    )

    result = producer.produce(
        create_incoming_signal(
            "HELLO TODOBA"
        ),
        open_position_count=0,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    assert result.status == "invalid_signal"
    assert result.task is None
    assert result.errors