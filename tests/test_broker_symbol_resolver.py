import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.broker.broker_symbol_resolver import (
    resolve_broker_symbol,
)


def main():

    print("=== BROKER SYMBOL RESOLVER TEST ===")

    symbol_map = {
        "GOLD": "GOLD.i#",
        "BTC": "BTCUSD",
    }

    symbol = resolve_broker_symbol(
        "gold",
        symbol_map,
    )

    print(symbol)

    print(symbol == "GOLD.i#")

    btc = resolve_broker_symbol(
        "BTC",
        symbol_map,
    )

    print(btc)

    print(btc == "BTCUSD")


if __name__ == "__main__":
    main()