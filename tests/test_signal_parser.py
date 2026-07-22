import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from backend.trading.parser.signal_parser import parse_signal


@pytest.mark.parametrize(
    (
        "message",
        "expected_order_type",
        "expected_entry",
    ),
    [
        (
            """
            BUY XAUUSD NOW
            SL: 3310
            TP: 3340
            """,
            "BUY NOW",
            None,
        ),
        (
            """
            SELL GOLD NOW
            SL: 3340
            TP: 3310
            """,
            "SELL NOW",
            None,
        ),
        (
            """
            BUY XAUUSD LIMIT
            ENTRY: 3320
            SL: 3310
            TP: 3340
            """,
            "BUY LIMIT",
            3320.0,
        ),
        (
            """
            SELL XAUUSD LIMIT
            ENTRY: 3340
            SL: 3350
            TP: 3310
            """,
            "SELL LIMIT",
            3340.0,
        ),
        (
            """
            BUY XAUUSD STOP
            ENTRY: 3340
            SL: 3320
            TP: 3370
            """,
            "BUY STOP",
            3340.0,
        ),
        (
            """
            SELL XAUUSD STOP
            ENTRY: 3310
            SL: 3330
            TP: 3280
            """,
            "SELL STOP",
            3310.0,
        ),
    ],
)
def test_parse_supported_signal(
    message,
    expected_order_type,
    expected_entry,
):
    signal = parse_signal(message)

    assert signal.order_type == expected_order_type
    assert signal.symbol == "XAUUSD"
    assert signal.entry == expected_entry
    assert signal.sl is not None
    assert signal.tp is not None


def test_parse_signal_accepts_supported_separators():
    signal = parse_signal(
        """
        BUY GOLD LIMIT
        ENTRY=3320
        SL 3310
        TP:3340
        """
    )

    assert signal.order_type == "BUY LIMIT"
    assert signal.symbol == "XAUUSD"
    assert signal.entry == 3320.0
    assert signal.sl == 3310.0
    assert signal.tp == 3340.0