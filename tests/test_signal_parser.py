import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.parser.signal_parser import parse_signal


def main():
    print("=== SIGNAL PARSER TEST ===")

    message_1 = """
BUY XAUUSD
ENTRY: 3320
SL: 3310
TP: 3340
"""

    signal_1 = parse_signal(message_1)

    print(signal_1)
    print(f"Signal 1 OK: {signal_1.symbol == 'XAUUSD' and signal_1.entry == 3320.0}")

    message_2 = """
BUY GOLD NOW
SL 3310
TP 3340
"""

    signal_2 = parse_signal(message_2)

    print(signal_2)
    print(f"Signal 2 OK: {signal_2.symbol == 'XAUUSD' and signal_2.entry is None}")


if __name__ == "__main__":
    main()