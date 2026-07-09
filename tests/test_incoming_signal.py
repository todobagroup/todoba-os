import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from datetime import datetime

from backend.trading.signal.incoming_signal import IncomingSignal


def main():

    print("=== INCOMING SIGNAL TEST ===")

    signal = IncomingSignal(
        source="telegram",
        message="BUY GOLD NOW SL 3330 TP 3345",
        received_at=datetime.now(),
        sender="demo_channel",
    )

    print(signal)

    print(signal.source == "telegram")
    print(signal.message.startswith("BUY GOLD"))


if __name__ == "__main__":
    main()