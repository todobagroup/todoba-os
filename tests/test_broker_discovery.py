import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import MetaTrader5 as mt5

from backend.trading.knowledge.broker_discovery import BrokerDiscovery


def main():

    print("=== BROKER DISCOVERY TEST ===")

    if not mt5.initialize():
        print("Connect failed.")
        return

    discovery = BrokerDiscovery()

    symbols = discovery.discover_symbols()

    print("Total Symbols:", len(symbols))

    mt5.shutdown()


if __name__ == "__main__":
    main()