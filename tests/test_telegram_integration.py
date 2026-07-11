"""
End-to-end dry-run tests for Telegram Integration Phase 1.

These tests do not connect to Telegram.
These tests do not connect to MT5.
These tests do not send live orders.
"""

from datetime import datetime, timezone

from backend.integrations.telegram_trading_pipeline import (
    TelegramTradingPipeline,
)
from backend.trading.profile.trading_profile import (
    TradingProfile,
)
from backend.trading.signal.incoming_signal import (
    IncomingSignal,
)


def create_profile() -> TradingProfile:
    return TradingProfile(
        profile_name="telegram_test",
        risk_percent=1.0,
        max_open_trades=1,
        allowed_symbols=("XAUUSD",),
        lot_policy_name="FIXED_001",
    )


def create_signal(
    message: str,
    message_id: int = 500,
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
        message_id=message_id,
    )


def test_valid_telegram_signal_creates_dry_run_plan():
    pipeline = TelegramTradingPipeline(
        create_profile()
    )

    incoming_signal = create_signal(
        "BUY GOLD NOW\n"
        "SL 3330\n"
        "TP 3345"
    )

    result = pipeline.process(
        incoming_signal
    )

    assert result["status"] == "planned"
    assert result["mode"] == "DRY_RUN"
    assert result["live_order_sent"] is False

    assert result["signal"]["symbol"] == "XAUUSD"
    assert result["signal"]["order_type"] == "BUY NOW"

    assert (
        result["execution_plan"]["lot"]
        == 0.01
    )

    assert (
        result["execution_plan"]["comment"]
        == "TODOBA:telegram_test"
    )


def test_invalid_message_is_rejected_safely():
    pipeline = TelegramTradingPipeline(
        create_profile()
    )

    incoming_signal = create_signal(
        "HELLO TODOBA"
    )

    result = pipeline.process(
        incoming_signal
    )

    assert result["status"] == "rejected"
    assert result["mode"] == "DRY_RUN"
    assert result["live_order_sent"] is False
    assert result["errors"]


def test_duplicate_telegram_message_is_ignored():
    pipeline = TelegramTradingPipeline(
        create_profile()
    )

    incoming_signal = create_signal(
        "SELL GOLD NOW\n"
        "SL 3345\n"
        "TP 3330"
    )

    first_result = pipeline.process(
        incoming_signal
    )

    second_result = pipeline.process(
        incoming_signal
    )

    assert first_result["status"] == "planned"
    assert second_result["status"] == "duplicate"

    assert pipeline.processed_count() == 1


def test_disallowed_symbol_is_rejected():
    profile = TradingProfile(
        profile_name="no_symbols_allowed",
        risk_percent=1.0,
        max_open_trades=1,
        allowed_symbols=(),
        lot_policy_name="FIXED_001",
    )

    pipeline = TelegramTradingPipeline(
        profile
    )

    incoming_signal = create_signal(
        "BUY GOLD NOW\n"
        "SL 3330\n"
        "TP 3345",
        message_id=501,
    )

    result = pipeline.process(
        incoming_signal
    )

    assert result["status"] == "rejected"
    assert result["mode"] == "DRY_RUN"
    assert result["live_order_sent"] is False

    assert "Symbol not allowed." in result["errors"]