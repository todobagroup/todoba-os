import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from datetime import datetime

from backend.trading.signal.incoming_signal import IncomingSignal
from backend.trading.signal.signal_record import SignalRecord
from backend.trading.signal.signal_status import SignalStatus


def main():

    print("=== SIGNAL LIFECYCLE TEST ===")

    signal = IncomingSignal(
        source="telegram",
        message="BUY GOLD SL 3330 TP 3345",
        received_at=datetime.now(),
    )


    record = SignalRecord(signal)


    print(record.status)

    record.status = SignalStatus.PROCESSING

    print(record.status)

    record.status = SignalStatus.EXECUTED

    print(record.status)

    print(record.status == SignalStatus.EXECUTED)


if __name__ == "__main__":
    main()