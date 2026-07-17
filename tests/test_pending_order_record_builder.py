import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import pytest

from backend.trading.models.order_result import (
    OrderResult,
)
from backend.trading.pending.pending_order_record_builder import (
    PendingOrderRecordBuilder,
)
from backend.trading.pending.pending_order_status import (
    PendingOrderStatus,
)


def create_order_result(
    *,
    success=True,
    order=1001,
):

    return OrderResult(
        success=success,
        retcode=10009,
        order=order,
        deal=None,
        volume=0.01,
        price=3300.0,
        comment="OK",
    )


def test_build_pending_order_record():

    builder = PendingOrderRecordBuilder()

    record = builder.build(
        pending_order_id="pending-001",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=3300.0,
        sl=3290.0,
        tp=3320.0,
        order_result=create_order_result(),
    )

    assert record.pending_order_id == "pending-001"
    assert record.order == 1001
    assert record.status == PendingOrderStatus.PLACED
    assert record.symbol == "XAUUSD"


def test_reject_unsuccessful_order():

    builder = PendingOrderRecordBuilder()

    with pytest.raises(ValueError):

        builder.build(
            pending_order_id="pending-001",
            symbol="XAUUSD",
            order_type="BUY LIMIT",
            volume=0.01,
            entry=3300.0,
            sl=3290.0,
            tp=3320.0,
            order_result=create_order_result(
                success=False,
            ),
        )


def test_reject_missing_order_ticket():

    builder = PendingOrderRecordBuilder()

    with pytest.raises(ValueError):

        builder.build(
            pending_order_id="pending-001",
            symbol="XAUUSD",
            order_type="BUY LIMIT",
            volume=0.01,
            entry=3300.0,
            sl=3290.0,
            tp=3320.0,
            order_result=create_order_result(
                order=None,
            ),
        )