import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.pending.pending_activation_bridge import (
    PendingActivationBridge,
)
from backend.trading.pending.pending_activation_runtime import (
    PendingActivationRuntime,
)
from backend.trading.pending.pending_broker_evidence_reader import (
    PendingBrokerEvidenceReader,
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
from backend.trading.pending.pending_order_repository import (
    PendingOrderRepository,
)
from backend.trading.pending.pending_order_status import (
    PendingOrderStatus,
)


class FakeEvidenceReader(PendingBrokerEvidenceReader):
    """
    Safe broker evidence substitute.
    """

    def __init__(
        self,
        *,
        status=PendingBrokerStatus.FILLED,
    ):
        self.status = status
        self.observe_count = 0

    def observe(
        self,
        record,
    ):
        self.observe_count += 1

        if (
            self.status
            == PendingBrokerStatus.FILLED
        ):
            return PendingOrderObservation(
                pending_order_id=(
                    record.pending_order_id
                ),
                order_ticket=record.order,
                status=self.status,
                opening_deal_ticket=9001,
            )

        return PendingOrder