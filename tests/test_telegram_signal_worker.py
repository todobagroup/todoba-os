import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from datetime import datetime

from backend.workers.telegram.telegram_signal_worker import TelegramSignalWorker
from backend.trading.signal.signal_gateway import SignalGateway
from backend.trading.signal.signal_queue import SignalQueue
from backend.trading.signal.incoming_signal import IncomingSignal


def main():

    print("=== TELEGRAM SIGNAL WORKER TEST ===")


    queue = SignalQueue()

    gateway = SignalGateway(queue)


    worker = TelegramSignalWorker(gateway)


    print(worker.start())


    signal = IncomingSignal(
        source="telegram",
        message="BUY GOLD SL 3330 TP 3345",
        received_at=datetime.now(),
    )


    print(worker.execute(signal))


    print(queue.size())


    print(queue.pop().source == "telegram")


    print(worker.stop())


if __name__ == "__main__":
    main()