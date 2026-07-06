import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.parser.signal_parser import parse_signal


def should_fail(message: str, title: str):
    try:
        parse_signal(message)
        print(f"[FAIL] {title}")
    except Exception as e:
        print(f"[PASS] {title} -> {e}")


print("=== NEGATIVE TESTS ===")

should_fail("""
BUY XAUUSD
TP:3340
""", "Missing SL")

should_fail("""
BUY XAUUSD
SL:3310
""", "Missing TP")

should_fail("""
BUY ABC
SL:3310
TP:3340
""", "Unknown Symbol")

should_fail("""
MUA XAUUSD
SL:3310
TP:3340
""", "Invalid Order Side")