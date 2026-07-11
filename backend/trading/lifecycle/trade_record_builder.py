"""
TODOBA Trade Record Builder

Builds TradeRecord from execution result.
"""

from backend.trading.lifecycle.trade_record import TradeRecord
from backend.trading.lifecycle.trade_status import TradeStatus


class TradeRecordBuilder:

    def build(
        self,
        *,
        trade_id,
        symbol,
        action,
        volume,
        order_result,
    ):

        status = TradeStatus.OPEN if order_result.success else TradeStatus.CREATED

        return TradeRecord(
            trade_id=trade_id,
            symbol=symbol,
            action=action,
            volume=volume,
            status=status,
            order=order_result.order,
            deal=order_result.deal,
        )

    def from_order_result(
        self,
        *,
        trade_id,
        symbol,
        action,
        volume,
        order_result,
    ):

        return self.build(
            trade_id=trade_id,
            symbol=symbol,
            action=action,
            volume=volume,
            order_result=order_result,
        )