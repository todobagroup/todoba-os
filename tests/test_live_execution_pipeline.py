import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import pytest

from backend.trading.models.order_result import (
    OrderResult,
)
from backend.trading.pending.pending_order_record import (
    PendingOrderRecord,
)
from backend.trading.pending.pending_order_record_builder import (
    PendingOrderRecordBuilder,
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


def test_pending_record_builder_returns_pending_record():

    record = PendingOrderRecordBuilder().build(
        pending_order_id="pending-001",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=3300.0,
        sl=3290.0,
        tp=3320.0,
        order_result=create_order_result(),
    )

    assert isinstance(
        record,
        PendingOrderRecord,
    )

    assert record.order == 1001


def test_pending_builder_requires_order_ticket():

    with pytest.raises(
        ValueError,
        match="no order ticket",
    ):
        PendingOrderRecordBuilder().build(
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


def test_pending_builder_rejects_failed_result():

    with pytest.raises(
        ValueError,
        match="unsuccessful broker result",
    ):
        PendingOrderRecordBuilder().build(
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