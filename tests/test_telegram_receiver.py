import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from backend.workers.telegram.telegram_receiver import TelegramReceiver


def main():

    print("=== TELEGRAM RECEIVER TEST ===")

    receiver = TelegramReceiver()

    signal = receiver.receive(
        message="BUY GOLD NOW\nSL 3330\nTP 3345",
        sender="demo_channel",
    )

    print(signal)

    print(signal.source == "telegram")
    print(signal.sender == "demo_channel")
    print(signal.message.startswith("BUY GOLD"))


if __name__ == "__main__":
    main()