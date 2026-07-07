import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import MetaTrader5 as mt5


def main():
    print("=== MT5 SYMBOL SEARCH ===")

    if not mt5.initialize():
        print("Connect failed.")
        return

    symbols = mt5.symbols_get()

    if symbols is None:
        print("No symbols found.")
        mt5.shutdown()
        return

    for symbol in symbols:
        name = symbol.name.upper()

        if "XAU" in name or "GOLD" in name:
            print(symbol.name)

    mt5.shutdown()


if __name__ == "__main__":
    main()