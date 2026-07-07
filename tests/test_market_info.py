import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.broker.mt5_client import MT5Client


def main():

    print("=== MARKET INFO TEST ===")

    client = MT5Client()

    if not client.connect():
        print("Connect failed.")
        return

    market = client.get_market_info("XAUUSD")

    print(market)

    print(market is not None)

    print(market.ask > market.bid)

    client.disconnect()


if __name__ == "__main__":
    main()