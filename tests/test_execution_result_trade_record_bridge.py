from backend.trading.lifecycle.trade_record_builder import (
    TradeRecordBuilder,
)

from backend.trading.lifecycle.trade_status import (
    TradeStatus,
)


class FakeOrderResult:

    def __init__(
        self,
        *,
        success,
        order,
        deal,
    ):
        self.success = success
        self.order = order
        self.deal = deal


def test_execution_result_creates_trade_record_identity():

    builder = TradeRecordBuilder()

    order_result = FakeOrderResult(
        success=True,
        order=123456,
        deal=789012,
    )

    record = builder.build(
        trade_id="proof054-001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        order_result=order_result,
    )

    assert record.trade_id == (
        "proof054-001"
    )

    assert record.symbol == (
        "XAUUSD"
    )

    assert record.action == (
        "BUY"
    )

    assert record.volume == (
        0.01
    )

    assert record.order == (
        123456
    )

    assert record.deal == (
        789012
    )

    assert record.status == (
        TradeStatus.OPEN
    )