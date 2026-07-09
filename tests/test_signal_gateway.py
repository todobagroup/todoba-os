import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from datetime import datetime

from backend.trading.signal.incoming_signal import IncomingSignal
from backend.trading.signal.signal_queue import SignalQueue
from backend.trading.signal.signal_gateway import SignalGateway


def main():

    print("=== SIGNAL GATEWAY TEST ===")

    queue = SignalQueue()

    gateway = SignalGateway(queue)

    signal = IncomingSignal(
        source="telegram",
        message="BUY GOLD SL 3330 TP 3345",
        received_at=datetime.now(),
    )

    result = gateway.receive(signal)

    print(result)
    print(queue.size())

    print(queue.pop().source == "telegram")


if __name__ == "__main__":
    main()