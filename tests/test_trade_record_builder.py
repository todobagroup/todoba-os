import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.lifecycle.trade_record_builder import TradeRecordBuilder
from backend.trading.lifecycle.trade_status import TradeStatus
from backend.trading.models.order_result import OrderResult


def main():

    print("=== TRADE RECORD BUILDER TEST ===")

    order_result = OrderResult(
        success=True,
        retcode=10009,
        order=123456,
        deal=654321,
        volume=0.01,
        price=3335.00,
        comment="Request executed",
    )

    builder = TradeRecordBuilder()

    record = builder.build(
        trade_id="TRD-000001",
        symbol="GOLD",
        action="BUY",
        volume=0.01,
        order_result=order_result,
    )

    print(record.trade_id)
    print(record.symbol)
    print(record.action)
    print(record.status)
    print(record.order)
    print(record.deal)

    print(record.status == TradeStatus.OPEN)


if __name__ == "__main__":
    main()