import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.lifecycle.trade_lifecycle import TradeLifecycle


def main():

    print("=== TRADE LIFECYCLE TEST ===")

    trade = TradeLifecycle(
        trade_id="TRD-000001"
    )

    print(trade.status.name)

    trade.executing()
    print(trade.status.name)

    trade.opened()
    print(trade.status.name)

    trade.closed()
    print(trade.status.name)


if __name__ == "__main__":
    main()