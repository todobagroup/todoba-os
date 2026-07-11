"""
Tests for TODOBA TelegramReceiver.
"""

import pytest

from backend.workers.telegram.telegram_receiver import (
    TelegramReceiver,
)


def test_receiver_creates_incoming_signal():
    receiver = TelegramReceiver()

    signal = receiver.receive(
        message="BUY GOLD NOW\nSL 3330\nTP 3345",
        sender="demo_channel",
        sender_id=101,
        chat_id=-100123,
        message_id=500,
    )

    assert signal.source == "telegram"
    assert signal.sender == "demo_channel"
    assert signal.sender_id == 101
    assert signal.chat_id == -100123
    assert signal.message_id == 500

    assert signal.message.startswith(
        "BUY GOLD"
    )

    assert signal.source_key() == (
        -100123,
        500,
    )


def test_receiver_trims_message():
    receiver = TelegramReceiver()

    signal = receiver.receive(
        message="  BUY GOLD NOW\nSL 3330\nTP 3345  "
    )

    assert signal.message == (
        "BUY GOLD NOW\nSL 3330\nTP 3345"
    )


def test_receiver_rejects_empty_message():
    receiver = TelegramReceiver()

    with pytest.raises(
        ValueError,
        match="Telegram message is required",
    ):
        receiver.receive("   ")