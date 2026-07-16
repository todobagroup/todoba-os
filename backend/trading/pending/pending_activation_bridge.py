"""
TODOBA Pending Activation Bridge

Converts broker evidence into an activation decision.

This component does not:

- modify repositories;
- persist trades;
- update timelines;
- communicate with MT5.
"""

from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)
from backend.trading.lifecycle.trade_status import (
    TradeStatus,
)
from backend.trading.pending.pending_activation_result import (
    PendingActivationResult,
)
from backend.trading.pending.pending_broker_status import (
    PendingBrokerStatus,
)
from backend.trading.pending.pending_order_observation import (
    PendingOrderObservation,
)
from backend.trading.pending.pending_order_record import (
    PendingOrderRecord,
)


class PendingActivationBridge:
    """
    Decide whether a pending order has become
    an open trade.
    """

    def activate(
        self,
        *,
        record: PendingOrderRecord,
        observation: PendingOrderObservation,
    ) -> PendingActivationResult:

        if not isinstance(
            record,
            PendingOrderRecord,
        ):
            raise TypeError(
                "record must be PendingOrderRecord."
            )

        if not isinstance(
            observation,
            PendingOrderObservation,
        ):
            raise TypeError(
                "observation must be PendingOrderObservation."
            )

        if (
            observation.status
            != PendingBrokerStatus.FILLED
        ):
            return PendingActivationResult(
                activated=False,
                reason="Pending order not activated.",
            )

        trade = TradeRecord(
            trade_id=record.pending_order_id,
            symbol=record.symbol,
            action=record.order_type,
            volume=record.volume,
            status=TradeStatus.OPEN,
            order=record.order,
            deal=observation.opening_deal_ticket,
        )

        return PendingActivationResult(
            activated=True,
            trade_record=trade,
        )