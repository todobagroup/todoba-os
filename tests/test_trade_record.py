import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.lifecycle.trade_record import TradeRecord
from backend.trading.lifecycle.trade_status import TradeStatus


def main():

    print("=== TRADE RECORD TEST ===")

    trade = TradeRecord(
        trade_id="TRD-000001",
        symbol="GOLD",
        action="BUY",
        volume=0.01,
    )

    print(trade.trade_id)
    print(trade.symbol)
    print(trade.action)
    print(trade.volume)
    print(trade.status == TradeStatus.CREATED)


if __name__ == "__main__":
    main()