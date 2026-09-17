"""
P9A4A2 ? MT5 Account Cashflow Attribution Evidence Enrichment.

Preserve raw broker context needed by future broker-qualified
external-funding classification.

This capability does NOT classify deposits or withdrawals.
"""

from collections import namedtuple
from datetime import UTC
from datetime import datetime

from backend.trading.lifecycle.mt5_account_cashflow_history_reader import (
    MT5AccountCashflowHistoryReader,
)


Deal = namedtuple(
    "Deal",
    (
        "ticket",
        "order",
        "time",
        "time_msc",
        "type",
        "entry",
        "magic",
        "position_id",
        "reason",
        "volume",
        "price",
        "profit",
        "commission",
        "swap",
        "fee",
        "symbol",
        "comment",
        "external_id",
    ),
)


class FakeMT5:
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1
    DEAL_TYPE_BALANCE = 2
    DEAL_TYPE_CREDIT = 3
    DEAL_TYPE_CHARGE = 4
    DEAL_TYPE_CORRECTION = 5
    DEAL_TYPE_BONUS = 6
    DEAL_TYPE_COMMISSION = 7
    DEAL_TYPE_COMMISSION_DAILY = 8
    DEAL_TYPE_COMMISSION_MONTHLY = 9
    DEAL_TYPE_COMMISSION_AGENT_DAILY = 10
    DEAL_TYPE_COMMISSION_AGENT_MONTHLY = 11
    DEAL_TYPE_INTEREST = 12
    DEAL_TYPE_BUY_CANCELED = 13
    DEAL_TYPE_SELL_CANCELED = 14

    def history_deals_get(
        self,
        date_from,
        date_to,
    ):
        return (
            Deal(
                ticket=2254467273,
                order=0,
                time=1788882804,
                time_msc=1788882804670,
                type=self.DEAL_TYPE_BALANCE,
                entry=0,
                magic=0,
                position_id=0,
                reason=0,
                volume=0.0,
                price=0.0,
                profit=8000.0,
                commission=0.0,
                swap=0.0,
                fee=0.0,
                symbol="",
                comment="Deposit to 68353796",
                external_id="",
            ),
        )


START = datetime(
    2026,
    9,
    8,
    tzinfo=UTC,
)

END = datetime(
    2026,
    9,
    9,
    tzinfo=UTC,
)


def _evidence():
    return MT5AccountCashflowHistoryReader(
        FakeMT5()
    ).read(
        observed_from=START,
        observed_to=END,
    )[0]


def test_preserves_raw_broker_attribution_context():
    item = _evidence()

    assert item.order_ticket == 0
    assert item.deal_entry == 0
    assert item.magic == 0
    assert item.position_id == 0
    assert item.deal_reason == 0
    assert item.volume == 0.0
    assert item.price == 0.0
    assert item.symbol == ""
    assert item.external_id == ""


def test_preserves_exact_broker_comment():
    item = _evidence()

    assert (
        item.comment
        == "Deposit to 68353796"
    )


def test_enrichment_does_not_create_classification_authority():
    item = _evidence()

    for forbidden in (
        "is_external_deposit",
        "is_external_withdrawal",
        "funding_direction",
        "customer_funding_kind",
        "upgrade_required",
        "cycle_id",
        "customer_id",
    ):
        assert not hasattr(
            item,
            forbidden,
        )
