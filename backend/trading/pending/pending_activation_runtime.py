"""
TODOBA Pending Activation Runtime

Coordinates pending-order activation.

This component owns the runtime flow:

PendingOrderRecord
        ↓
Broker Evidence
        ↓
Activation Bridge
        ↓
Trading Runtime
"""

from backend.trading.pending.pending_activation_bridge import (
    PendingActivationBridge,
)
from backend.trading.pending.pending_broker_evidence_reader import (
    PendingBrokerEvidenceReader,
)
from backend.trading.pending.pending_order_repository import (
    PendingOrderRepository,
)
from backend.trading.pending.pending_order_status import (
    PendingOrderStatus,
)
from backend.trading.runtime.trading_runtime import (
    TradingRuntime,
)


class PendingActivationRuntime:
    """
    Runtime coordinator for pending-order activation.
    """

    def __init__(
        self,
        *,
        repository: PendingOrderRepository,
        evidence_reader: PendingBrokerEvidenceReader,
        activation_bridge: PendingActivationBridge,
        trading_runtime: TradingRuntime,
    ):
        self.repository = repository
        self.evidence_reader = evidence_reader
        self.activation_bridge = activation_bridge
        self.trading_runtime = trading_runtime

    def process(self) -> int:
        """
        Process every pending order once.

        Successfully activated pending orders are
        registered as open trades and removed from the
        pending repository.

        Returns the number of activated trades.
        """

        activated = 0

        for record in self.repository.all():

            observation = (
                self.evidence_reader.observe(
                    record
                )
            )

            result = (
                self.activation_bridge.activate(
                    record=record,
                    observation=observation,
                )
            )

            if not result.activated:
                continue

            self.trading_runtime.register_open_trade(
                result.trade_record
            )

            record.status = (
                PendingOrderStatus.TRIGGERED
            )

            self.repository.remove(
                record.pending_order_id
            )

            activated += 1

        return activated