import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.broker.mt5_client import MT5Client


def main():
    print("=== MT5 CLIENT TEST ===")

    client = MT5Client()

    connected = client.connect()

    print("Connected:", connected)

    print("Is connected:", client.is_connected())

    client.disconnect()

    print("Disconnected.")


if __name__ == "__main__":
    main()