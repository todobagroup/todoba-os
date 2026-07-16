import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from backend.trading.pending.pending_broker_evidence_reader import (
    PendingBrokerEvidenceReader,
)
from backend.trading.pending.pending_broker_status import (
    PendingBrokerStatus,
)
from backend.trading.pending.pending_order_record import (
    PendingOrderRecord,
)
from backend.trading.pending.pending_order_status import (
    PendingOrderStatus,
)


class FakeOrder:
    def __init__(
        self,
        *,
        state=1,
        position_id=0,
    ):
        self.state = state
        self.position_id = position_id


class FakeMT5:
    def __init__(self, orders):
        self._orders = orders

    def orders_get(
        self,
        *,
        ticket,
    ):
        return self._orders


def test_observe_returns_active_when_order_exists():

    reader = PendingBrokerEvidenceReader(
        FakeMT5(
            [
                FakeOrder(
                    state=5,
                    position_id=0,
                )
            ]
        )
    )

    record = PendingOrderRecord(
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

    observation = reader.observe(record)

    assert (
        observation.status
        == PendingBrokerStatus.ACTIVE
    )

    assert observation.order_ticket == 1001

    assert observation.active_order_found is True


def test_observe_returns_unknown_when_order_missing():

    reader = PendingBrokerEvidenceReader(
        FakeMT5([])
    )

    record = PendingOrderRecord(
        pending_order_id="pending-002",
        symbol="XAUUSD",
        order_type="BUY_LIMIT",
        volume=0.01,
        entry=3300.0,
        sl=3290.0,
        tp=3320.0,
        status=PendingOrderStatus.PLACED,
        order=2002,
    )

    observation = reader.observe(record)

    assert (
        observation.status
        == PendingBrokerStatus.UNKNOWN
    )

    assert observation.active_order_found is False


def test_observe_without_order_ticket_returns_unknown():

    reader = PendingBrokerEvidenceReader(
        FakeMT5([])
    )

    record = PendingOrderRecord(
        pending_order_id="pending-003",
        symbol="XAUUSD",
        order_type="BUY_LIMIT",
        volume=0.01,
        entry=3300.0,
        sl=3290.0,
        tp=3320.0,
        status=PendingOrderStatus.CREATED,
        order=None,
    )

    observation = reader.observe(record)

    assert (
        observation.status
        == PendingBrokerStatus.UNKNOWN
    )

    assert observation.order_ticket is None