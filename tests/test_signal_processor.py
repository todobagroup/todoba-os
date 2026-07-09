import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from datetime import datetime

from backend.trading.signal.incoming_signal import IncomingSignal
from backend.trading.signal.signal_processor import SignalProcessor


def main():

    print("=== SIGNAL PROCESSOR TEST ===")

    incoming = IncomingSignal(
        source="telegram",
        message="""
BUY GOLD NOW
SL 3330
TP 3345
""",
        received_at=datetime.now(),
        sender="demo_channel",
    )

    processor = SignalProcessor()

    signal = processor.process(incoming)

    print(signal)

    print(signal.order_type == "BUY NOW")
    print(signal.symbol == "XAUUSD")
    print(signal.sl == 3330)
    print(signal.tp == 3345)


if __name__ == "__main__":
    main()