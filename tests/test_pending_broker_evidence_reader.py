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
        ticket,
        state,
        position_id=0,
    ):
        self.ticket = ticket
        self.state = state
        self.position_id = position_id


class FakeDeal:
    def __init__(
        self,
        *,
        ticket,
        order,
        position_id,
        entry,
        deal_type,
        time_msc=0,
        time=0,
    ):
        self.ticket = ticket
        self.order = order
        self.position_id = position_id
        self.entry = entry
        self.type = deal_type
        self.time_msc = time_msc
        self.time = time


class FakeMT5:
    ORDER_STATE_FILLED = 4
    ORDER_STATE_CANCELED = 5
    ORDER_STATE_REJECTED = 6
    ORDER_STATE_EXPIRED = 7

    DEAL_ENTRY_IN = 0
    DEAL_ENTRY_INOUT = 2

    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1

    def __init__(
        self,
        *,
        active_orders=(),
        historical_orders=(),
        deals=(),
    ):
        self.active_orders = active_orders
        self.historical_orders = historical_orders
        self.deals = deals

    def orders_get(
        self,
        *,
        ticket,
    ):
        return self.active_orders

    def history_orders_get(
        self,
        *,
        ticket,
    ):
        return self.historical_orders

    def history_deals_get(
        self,
        *,
        ticket,
    ):
        return self.deals


def create_record(
    *,
    pending_order_id="pending-001",
    order=1001,
):

    return PendingOrderRecord(
        pending_order_id=pending_order_id,
        symbol="XAUUSD",
        order_type="BUY_LIMIT",
        volume=0.01,
        entry=3300.0,
        sl=3290.0,
        tp=3320.0,
        status=PendingOrderStatus.PLACED,
        order=order,
    )


def test_observe_returns_active_when_order_exists():

    reader = PendingBrokerEvidenceReader(
        FakeMT5(
            active_orders=(
                FakeOrder(
                    ticket=1001,
                    state=1,
                ),
            )
        )
    )

    observation = reader.observe(
        create_record()
    )

    assert (
        observation.status
        == PendingBrokerStatus.ACTIVE
    )

    assert observation.active_order_found is True
    assert observation.order_ticket == 1001


def test_observe_returns_filled_with_opening_deal():

    reader = PendingBrokerEvidenceReader(
        FakeMT5(
            historical_orders=(
                FakeOrder(
                    ticket=1001,
                    state=FakeMT5.ORDER_STATE_FILLED,
                    position_id=5001,
                ),
            ),
            deals=(
                FakeDeal(
                    ticket=9001,
                    order=1001,
                    position_id=5001,
                    entry=FakeMT5.DEAL_ENTRY_IN,
                    deal_type=FakeMT5.DEAL_TYPE_BUY,
                ),
            ),
        )
    )

    observation = reader.observe(
        create_record()
    )

    assert (
        observation.status
        == PendingBrokerStatus.FILLED
    )

    assert observation.historical_order_found is True
    assert observation.opening_deal_found is True
    assert observation.opening_deal_ticket == 9001
    assert observation.position_id == 5001


def test_observe_returns_cancelled():

    reader = PendingBrokerEvidenceReader(
        FakeMT5(
            historical_orders=(
                FakeOrder(
                    ticket=1001,
                    state=FakeMT5.ORDER_STATE_CANCELED,
                ),
            )
        )
    )

    observation = reader.observe(
        create_record()
    )

    assert (
        observation.status
        == PendingBrokerStatus.CANCELLED
    )


def test_observe_returns_expired():

    reader = PendingBrokerEvidenceReader(
        FakeMT5(
            historical_orders=(
                FakeOrder(
                    ticket=1001,
                    state=FakeMT5.ORDER_STATE_EXPIRED,
                ),
            )
        )
    )

    observation = reader.observe(
        create_record()
    )

    assert (
        observation.status
        == PendingBrokerStatus.EXPIRED
    )


def test_observe_returns_rejected():

    reader = PendingBrokerEvidenceReader(
        FakeMT5(
            historical_orders=(
                FakeOrder(
                    ticket=1001,
                    state=FakeMT5.ORDER_STATE_REJECTED,
                ),
            )
        )
    )

    observation = reader.observe(
        create_record()
    )

    assert (
        observation.status
        == PendingBrokerStatus.REJECTED
    )


def test_observe_returns_unknown_when_no_broker_evidence():

    reader = PendingBrokerEvidenceReader(
        FakeMT5()
    )

    observation = reader.observe(
        create_record()
    )

    assert (
        observation.status
        == PendingBrokerStatus.UNKNOWN
    )

    assert observation.active_order_found is False
    assert observation.historical_order_found is False


def test_observe_returns_unknown_without_order_ticket():

    reader = PendingBrokerEvidenceReader(
        FakeMT5()
    )

    observation = reader.observe(
        create_record(
            pending_order_id="pending-002",
            order=None,
        )
    )

    assert (
        observation.status
        == PendingBrokerStatus.UNKNOWN
    )

    assert observation.order_ticket is None


def test_filled_order_without_opening_deal_is_unknown():

    reader = PendingBrokerEvidenceReader(
        FakeMT5(
            historical_orders=(
                FakeOrder(
                    ticket=1001,
                    state=FakeMT5.ORDER_STATE_FILLED,
                ),
            ),
            deals=(),
        )
    )

    observation = reader.observe(
        create_record()
    )

    assert (
        observation.status
        == PendingBrokerStatus.UNKNOWN
    )

    assert observation.historical_order_found is True
    assert observation.opening_deal_found is False