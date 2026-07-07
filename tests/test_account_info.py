import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.broker.mt5_client import MT5Client


def main():

    print("=== ACCOUNT INFO TEST ===")

    client = MT5Client()

    if not client.connect():
        print("Connect failed.")
        return

    account = client.get_account_info()

    print(account)

    print(account is not None)

    print(account.balance > 0)

    client.disconnect()


if __name__ == "__main__":
    main()