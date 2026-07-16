"""
TODOBA Pending Broker Evidence Reader

Reads broker evidence for one organizational pending order.

This component only observes broker state.

It does not:
- modify PendingOrderRecord;
- create TradeRecord;
- update repositories;
- perform lifecycle transitions.
"""

from backend.trading.pending.pending_broker_status import (
    PendingBrokerStatus,
)
from backend.trading.pending.pending_order_observation import (
    PendingOrderObservation,
)
from backend.trading.pending.pending_order_record import (
    PendingOrderRecord,
)


class PendingBrokerEvidenceReader:
    """
    Read broker evidence for one pending order.
    """

    def __init__(
        self,
        mt5_module,
    ):
        self.mt5 = mt5_module

    def observe(
        self,
        record: PendingOrderRecord,
    ) -> PendingOrderObservation:

        if not isinstance(
            record,
            PendingOrderRecord,
        ):
            raise TypeError(
                "observe requires PendingOrderRecord."
            )

        if record.order is None:
            return PendingOrderObservation(
                pending_order_id=record.pending_order_id,
                order_ticket=None,
                status=PendingBrokerStatus.UNKNOWN,
                error="Pending order has no broker order ticket.",
            )

        orders = self.mt5.orders_get(
            ticket=record.order,
        )

        if orders is None:
            return PendingOrderObservation(
                pending_order_id=record.pending_order_id,
                order_ticket=record.order,
                status=PendingBrokerStatus.UNKNOWN,
                error="orders_get failed.",
            )

        if len(orders) > 0:

            broker_order = orders[0]

            return PendingOrderObservation(
                pending_order_id=record.pending_order_id,
                order_ticket=record.order,
                status=PendingBrokerStatus.ACTIVE,
                broker_order_state=getattr(
                    broker_order,
                    "state",
                    None,
                ),
                position_id=getattr(
                    broker_order,
                    "position_id",
                    None,
                ),
                active_order_found=True,
            )

        return PendingOrderObservation(
            pending_order_id=record.pending_order_id,
            order_ticket=record.order,
            status=PendingBrokerStatus.UNKNOWN,
        )