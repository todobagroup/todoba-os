import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.lifecycle.trade_status import (
    TradeStatus,
)
from backend.trading.pending.pending_activation_bridge import (
    PendingActivationBridge,
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
from backend.trading.pending.pending_order_status import (
    PendingOrderStatus,
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


def test_pending_order_not_activated():

    bridge = PendingActivationBridge()

    result = bridge.activate(
        record=create_record(),
        observation=PendingOrderObservation(
            pending_order_id="pending-001",
            order_ticket=1001,
            status=PendingBrokerStatus.ACTIVE,
        ),
    )

    assert result.activated is False

    assert result.trade_record is None


def test_pending_order_becomes_trade():

    bridge = PendingActivationBridge()

    result = bridge.activate(
        record=create_record(),
        observation=PendingOrderObservation(
            pending_order_id="pending-001",
            order_ticket=1001,
            status=PendingBrokerStatus.FILLED,
            opening_deal_ticket=9001,
        ),
    )

    assert result.activated is True

    assert result.trade_record is not None

    assert (
        result.trade_record.status
        == TradeStatus.OPEN
    )

    assert result.trade_record.deal == 9001