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
            return self._unknown(
                record,
                error=(
                    "Pending order has no "
                    "broker order ticket."
                ),
            )

        active_orders = self.mt5.orders_get(
            ticket=record.order,
        )

        if active_orders is None:
            return self._unknown(
                record,
                error="orders_get failed.",
            )

        if active_orders:
            broker_order = active_orders[0]

            return PendingOrderObservation(
                pending_order_id=(
                    record.pending_order_id
                ),
                order_ticket=record.order,
                status=PendingBrokerStatus.ACTIVE,
                broker_order_state=getattr(
                    broker_order,
                    "state",
                    None,
                ),
                position_id=self._optional_positive_int(
                    getattr(
                        broker_order,
                        "position_id",
                        None,
                    )
                ),
                active_order_found=True,
            )

        historical_orders = (
            self.mt5.history_orders_get(
                ticket=record.order,
            )
        )

        if historical_orders is None:
            return self._unknown(
                record,
                error="history_orders_get failed.",
            )

        historical_order = self._find_order(
            historical_orders,
            record.order,
        )

        if historical_order is None:
            return self._unknown(
                record,
                error=(
                    "No active or historical "
                    "broker order was found."
                ),
            )

        broker_state = getattr(
            historical_order,
            "state",
            None,
        )

        if broker_state == getattr(
            self.mt5,
            "ORDER_STATE_CANCELED",
            object(),
        ):
            return self._historical_observation(
                record=record,
                broker_order=historical_order,
                status=(
                    PendingBrokerStatus.CANCELLED
                ),
            )

        if broker_state == getattr(
            self.mt5,
            "ORDER_STATE_EXPIRED",
            object(),
        ):
            return self._historical_observation(
                record=record,
                broker_order=historical_order,
                status=(
                    PendingBrokerStatus.EXPIRED
                ),
            )

        if broker_state == getattr(
            self.mt5,
            "ORDER_STATE_REJECTED",
            object(),
        ):
            return self._historical_observation(
                record=record,
                broker_order=historical_order,
                status=(
                    PendingBrokerStatus.REJECTED
                ),
            )

        if broker_state != getattr(
            self.mt5,
            "ORDER_STATE_FILLED",
            object(),
        ):
            return self._historical_observation(
                record=record,
                broker_order=historical_order,
                status=PendingBrokerStatus.UNKNOWN,
                error=(
                    "Unsupported historical "
                    "broker order state."
                ),
            )

        deals = self.mt5.history_deals_get(
            ticket=record.order,
        )

        if deals is None:
            return self._historical_observation(
                record=record,
                broker_order=historical_order,
                status=PendingBrokerStatus.UNKNOWN,
                error="history_deals_get failed.",
            )

        opening_deal = self._find_opening_deal(
            deals,
            record.order,
        )

        if opening_deal is None:
            return self._historical_observation(
                record=record,
                broker_order=historical_order,
                status=PendingBrokerStatus.UNKNOWN,
                error=(
                    "Filled order has no valid "
                    "opening deal evidence."
                ),
            )

        return PendingOrderObservation(
            pending_order_id=(
                record.pending_order_id
            ),
            order_ticket=record.order,
            status=PendingBrokerStatus.FILLED,
            broker_order_state=broker_state,
            position_id=self._optional_positive_int(
                getattr(
                    opening_deal,
                    "position_id",
                    None,
                )
            ),
            opening_deal_ticket=(
                self._optional_positive_int(
                    getattr(
                        opening_deal,
                        "ticket",
                        None,
                    )
                )
            ),
            opening_deal_entry=getattr(
                opening_deal,
                "entry",
                None,
            ),
            opening_deal_type=getattr(
                opening_deal,
                "type",
                None,
            ),
            historical_order_found=True,
            opening_deal_found=True,
        )

    def _find_order(
        self,
        orders,
        order_ticket: int,
    ):
        for order in orders:
            if getattr(
                order,
                "ticket",
                None,
            ) == order_ticket:
                return order

        return None

    def _find_opening_deal(
        self,
        deals,
        order_ticket: int,
    ):
        opening_entries = {
            getattr(
                self.mt5,
                "DEAL_ENTRY_IN",
                None,
            ),
            getattr(
                self.mt5,
                "DEAL_ENTRY_INOUT",
                None,
            ),
        }

        trading_types = {
            getattr(
                self.mt5,
                "DEAL_TYPE_BUY",
                None,
            ),
            getattr(
                self.mt5,
                "DEAL_TYPE_SELL",
                None,
            ),
        }

        candidates = []

        for deal in deals:
            if getattr(
                deal,
                "order",
                None,
            ) != order_ticket:
                continue

            if getattr(
                deal,
                "entry",
                None,
            ) not in opening_entries:
                continue

            if getattr(
                deal,
                "type",
                None,
            ) not in trading_types:
                continue

            position_id = (
                self._optional_positive_int(
                    getattr(
                        deal,
                        "position_id",
                        None,
                    )
                )
            )

            if position_id is None:
                continue

            candidates.append(deal)

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda deal: (
                getattr(
                    deal,
                    "time_msc",
                    0,
                ),
                getattr(
                    deal,
                    "time",
                    0,
                ),
                getattr(
                    deal,
                    "ticket",
                    0,
                ),
            ),
        )

    def _historical_observation(
        self,
        *,
        record: PendingOrderRecord,
        broker_order,
        status: PendingBrokerStatus,
        error: str | None = None,
    ) -> PendingOrderObservation:

        return PendingOrderObservation(
            pending_order_id=(
                record.pending_order_id
            ),
            order_ticket=record.order,
            status=status,
            broker_order_state=getattr(
                broker_order,
                "state",
                None,
            ),
            position_id=self._optional_positive_int(
                getattr(
                    broker_order,
                    "position_id",
                    None,
                )
            ),
            historical_order_found=True,
            error=error,
        )

    def _unknown(
        self,
        record: PendingOrderRecord,
        *,
        error: str,
    ) -> PendingOrderObservation:

        return PendingOrderObservation(
            pending_order_id=(
                record.pending_order_id
            ),
            order_ticket=record.order,
            status=PendingBrokerStatus.UNKNOWN,
            error=error,
        )

    def _optional_positive_int(
        self,
        value,
    ) -> int | None:

        if value in (
            None,
            0,
        ):
            return None

        value = int(value)

        if value <= 0:
            return None

        return value