"""
TODOBA Production Event Logger Tests
"""

from backend.logging.event import (
    ProductionEvent,
)
from backend.logging.event_logger import (
    ProductionEventLogger,
)


def test_logger_emits_event(capsys):

    logger = ProductionEventLogger()

    event = ProductionEvent(
        level="INFO",
        department="Trading",
        message="Department started.",
    )

    logger.emit(event)

    captured = capsys.readouterr()

    assert "INFO" in captured.out
    assert "Trading" in captured.out
    assert "Department started." in captured.out


def test_logger_prints_context(capsys):

    logger = ProductionEventLogger()

    event = ProductionEvent(
        level="WARNING",
        department="Risk",
        message="Spread exceeded.",
        context={
            "spread": 42,
            "symbol": "XAUUSD",
        },
    )

    logger.emit(event)

    captured = capsys.readouterr()

    assert "spread" in captured.out
    assert "42" in captured.out
    assert "XAUUSD" in captured.out