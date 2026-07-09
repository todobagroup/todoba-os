import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from datetime import datetime

from backend.trading.signal.incoming_signal import IncomingSignal
from backend.trading.signal.signal_queue import SignalQueue


def main():

    print("=== SIGNAL QUEUE TEST ===")

    queue = SignalQueue()

    signal = IncomingSignal(
        source="telegram",
        message="BUY GOLD SL 3330 TP 3345",
        received_at=datetime.now(),
    )

    queue.push(signal)

    print(queue.size())

    result = queue.pop()

    print(result)

    print(queue.size() == 0)


if __name__ == "__main__":
    main()