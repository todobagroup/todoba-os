"""
Tests for TODOBA TelegramSignalWorker.
"""

from datetime import datetime, timezone

import pytest

from backend.trading.signal.incoming_signal import (
    IncomingSignal,
)
from backend.trading.signal.signal_gateway import (
    SignalGateway,
)
from backend.trading.signal.signal_queue import (
    SignalQueue,
)
from backend.workers.telegram.telegram_signal_worker import (
    TelegramSignalWorker,
)


def create_incoming_signal() -> IncomingSignal:
    return IncomingSignal(
        source="telegram",
        message=(
            "BUY GOLD NOW\n"
            "SL 3330\n"
            "TP 3345"
        ),
        received_at=datetime.now(
            timezone.utc
        ),
        sender="demo_channel",
        chat_id=-100123,
        message_id=500,
    )


def test_worker_sends_signal_to_gateway():
    queue = SignalQueue()
    gateway = SignalGateway(queue)

    worker = TelegramSignalWorker(
        gateway
    )

    assert worker.start() is True

    signal = create_incoming_signal()

    assert worker.execute(signal) is True
    assert queue.size() == 1
    assert queue.pop() == signal

    assert worker.stop() is True


def test_worker_rejects_execution_when_stopped():
    queue = SignalQueue()
    gateway = SignalGateway(queue)

    worker = TelegramSignalWorker(
        gateway
    )

    with pytest.raises(
        RuntimeError,
        match="Worker is not running",
    ):
        worker.execute(
            create_incoming_signal()
        )


def test_worker_rejects_invalid_task_type():
    queue = SignalQueue()
    gateway = SignalGateway(queue)

    worker = TelegramSignalWorker(
        gateway
    )

    worker.start()

    with pytest.raises(
        TypeError,
        match="requires IncomingSignal",
    ):
        worker.execute(
            "not-an-incoming-signal"
        )