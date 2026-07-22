import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from backend.trading.parser.signal_parser import parse_signal


@pytest.mark.parametrize(
    "message",
    [
        "",
        "BUY",
        "BUY XAUUSD",
        "BUY XAUUSD UNKNOWN\nSL:3310\nTP:3340",
        "BUY ABC NOW\nSL:3310\nTP:3340",
        "MUA XAUUSD NOW\nSL:3310\nTP:3340",
        "BUY XAUUSD NOW\nTP:3340",
        "BUY XAUUSD NOW\nSL:3310",
        "BUY XAUUSD LIMIT\nSL:3310\nTP:3340",
        "SELL XAUUSD STOP\nSL:3330\nTP:3280",
    ],
)
def test_parse_signal_invalid_messages(message):
    with pytest.raises((TypeError, ValueError)):
        parse_signal(message)