"""
TODOBA Pending Order Record Builder

Builds PendingOrderRecord from a successful
broker pending-order result.
"""

from backend.trading.models.order_result import (
    OrderResult,
)
from backend.trading.pending.pending_order_record import (
    PendingOrderRecord,
)
from backend.trading.pending.pending_order_status import (
    PendingOrderStatus,
)


class PendingOrderRecordBuilder:
    """
    Build one organizational pending-order record.
    """

    def build(
        self,
        *,
        pending_order_id: str,
        symbol: str,
        order_type: str,
        volume: float,
        entry: float,
        sl: float,
        tp: float,
        order_result: OrderResult,
    ) -> PendingOrderRecord:

        if not isinstance(
            order_result,
            OrderResult,
        ):
            raise TypeError(
                "order_result must be OrderResult."
            )

        if not order_result.success:
            raise ValueError(
                "Cannot build pending order from "
                "unsuccessful broker result."
            )

        if order_result.order is None:
            raise ValueError(
                "Pending broker result has no "
                "order ticket."
            )

        return PendingOrderRecord(
            pending_order_id=pending_order_id,
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            entry=entry,
            sl=sl,
            tp=tp,
            status=PendingOrderStatus.PLACED,
            order=order_result.order,
        )