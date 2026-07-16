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

    def __init__(self):
        pass

    def observe(self, record):
        return PendingOrderObservation(
            pending_order_id=record.pending_order_id,
            order_ticket=record.order,
            status=PendingBrokerStatus.FILLED,
            opening_deal_ticket=9001,
        )


class FakeTradingRuntime:

    def __init__(self):
        self.registered = []

    def register_open_trade(
        self,
        trade_record,
    ):
        self.registered.append(
            trade_record
        )


def create_record():

    return PendingOrderRecord(
        pending_order_id="pending-001",
        symbol="XAUUSD",
        order_type="BUY_LIMIT",
        volume=0.01,
        entry=3300.0,
        sl=3290.0,
        tp=3320.0,
        status=PendingOrderStatus.PLACED,
        order=1001,
    )


def test_process_activates_pending_order():

    repository = PendingOrderRepository()

    record = create_record()

    repository.save(record)

    trading_runtime = FakeTradingRuntime()

    runtime = PendingActivationRuntime(
        repository=repository,
        evidence_reader=FakeEvidenceReader(),
        activation_bridge=PendingActivationBridge(),
        trading_runtime=trading_runtime,
    )

    activated = runtime.process()

    assert activated == 1

    assert (
        record.status
        == PendingOrderStatus.TRIGGERED
    )

    assert len(trading_runtime.registered) == 1


def test_process_returns_zero_when_repository_empty():

    repository = PendingOrderRepository()

    runtime = PendingActivationRuntime(
        repository=repository,
        evidence_reader=FakeEvidenceReader(),
        activation_bridge=PendingActivationBridge(),
        trading_runtime=FakeTradingRuntime(),
    )

    assert runtime.process() == 0