import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.broker.mt5_client import MT5Client
from backend.trading.broker.mt5_safety import MT5Safety


def main():

    print("=== MT5 SAFETY TEST ===")

    client = MT5Client()

    connected = client.connect()

    print("Connected:", connected)

    safety = MT5Safety()

    result = safety.validate()

    print(result)

    client.disconnect()


if __name__ == "__main__":
    main()