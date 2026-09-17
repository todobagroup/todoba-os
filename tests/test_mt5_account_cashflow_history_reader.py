"""
P9A4A ? Authoritative MT5 Account Cashflow Evidence Reader.

Boundary:

MT5 deal history
->
immutable normalized account-level cashflow evidence

This owner reads broker account operations.

It does NOT decide whether an event is:
- customer external deposit
- customer external withdrawal
- licensed-cap violation
- upgrade-required
- grace eligible

That commercial classification belongs to later capabilities.

Trading BUY / SELL deals are explicitly excluded.
"""

from collections import namedtuple
from datetime import UTC
from datetime import datetime
from decimal import Decimal

import pytest

from backend.trading.lifecycle.mt5_account_cashflow_history_reader import (
    MT5AccountCashflowEvidence,
    MT5AccountCashflowHistoryReader,
)


Deal = namedtuple(
    "Deal",
    (
        "ticket",
        "time",
        "time_msc",
        "type",
        "profit",
        "comment",
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

    def __init__(
        self,
        *,
        deals=(),
        fail=False,
    ):
        self.deals = deals
        self.fail = fail
        self.requested_from = None
        self.requested_to = None

    def history_deals_get(
        self,
        date_from,
        date_to,
    ):
        self.requested_from = date_from
        self.requested_to = date_to

        if self.fail:
            return None

        return self.deals

    def last_error(self):
        return (
            500,
            "fake-history-error",
        )


START = datetime(
    2026,
    9,
    17,
    0,
    0,
    tzinfo=UTC,
)

END = datetime(
    2026,
    9,
    18,
    0,
    0,
    tzinfo=UTC,
)


def deal(
    *,
    ticket,
    deal_type,
    amount,
    time=1_789_588_800,
    time_msc=1_789_588_800_000,
    comment="",
):
    return Deal(
        ticket=ticket,
        time=time,
        time_msc=time_msc,
        type=deal_type,
        profit=amount,
        comment=comment,
    )


def test_reader_returns_account_cashflow_evidence_only():
    fake_mt5 = FakeMT5(
        deals=(
            deal(
                ticket=1001,
                deal_type=FakeMT5.DEAL_TYPE_BUY,
                amount=25.0,
            ),
            deal(
                ticket=1002,
                deal_type=FakeMT5.DEAL_TYPE_BALANCE,
                amount=500.0,
                comment="Deposit",
            ),
            deal(
                ticket=1003,
                deal_type=FakeMT5.DEAL_TYPE_SELL,
                amount=-10.0,
            ),
            deal(
                ticket=1004,
                deal_type=FakeMT5.DEAL_TYPE_COMMISSION,
                amount=-3.5,
                comment="Broker commission",
            ),
        )
    )

    reader = MT5AccountCashflowHistoryReader(
        fake_mt5
    )

    evidence = reader.read(
        observed_from=START,
        observed_to=END,
    )

    assert fake_mt5.requested_from == START
    assert fake_mt5.requested_to == END

    assert [
        item.deal_ticket
        for item in evidence
    ] == [
        1002,
        1004,
    ]

    assert all(
        isinstance(
            item,
            MT5AccountCashflowEvidence,
        )
        for item in evidence
    )


@pytest.mark.parametrize(
    (
        "deal_type",
        "expected_kind",
    ),
    [
        (
            FakeMT5.DEAL_TYPE_BALANCE,
            "balance",
        ),
        (
            FakeMT5.DEAL_TYPE_CREDIT,
            "credit",
        ),
        (
            FakeMT5.DEAL_TYPE_CHARGE,
            "charge",
        ),
        (
            FakeMT5.DEAL_TYPE_CORRECTION,
            "correction",
        ),
        (
            FakeMT5.DEAL_TYPE_BONUS,
            "bonus",
        ),
        (
            FakeMT5.DEAL_TYPE_COMMISSION,
            "commission",
        ),
        (
            FakeMT5.DEAL_TYPE_COMMISSION_DAILY,
            "commission_daily",
        ),
        (
            FakeMT5.DEAL_TYPE_COMMISSION_MONTHLY,
            "commission_monthly",
        ),
        (
            FakeMT5.DEAL_TYPE_COMMISSION_AGENT_DAILY,
            "commission_agent_daily",
        ),
        (
            FakeMT5.DEAL_TYPE_COMMISSION_AGENT_MONTHLY,
            "commission_agent_monthly",
        ),
        (
            FakeMT5.DEAL_TYPE_INTEREST,
            "interest",
        ),
    ],
)
def test_reader_preserves_account_cashflow_kind(
    deal_type,
    expected_kind,
):
    reader = MT5AccountCashflowHistoryReader(
        FakeMT5(
            deals=(
                deal(
                    ticket=2001,
                    deal_type=deal_type,
                    amount=10.25,
                ),
            )
        )
    )

    result = reader.read(
        observed_from=START,
        observed_to=END,
    )

    assert len(result) == 1

    assert (
        result[0].cashflow_kind
        == expected_kind
    )

    assert (
        result[0].raw_deal_type
        == deal_type
    )


def test_reader_preserves_signed_exact_decimal_amount():
    reader = MT5AccountCashflowHistoryReader(
        FakeMT5(
            deals=(
                deal(
                    ticket=3001,
                    deal_type=FakeMT5.DEAL_TYPE_BALANCE,
                    amount=-125.75,
                    comment="Withdrawal",
                ),
            )
        )
    )

    result = reader.read(
        observed_from=START,
        observed_to=END,
    )

    assert (
        result[0].amount
        == Decimal("-125.75")
    )

    assert (
        result[0].comment
        == "Withdrawal"
    )


def test_reader_preserves_broker_deal_identity_and_time():
    reader = MT5AccountCashflowHistoryReader(
        FakeMT5(
            deals=(
                deal(
                    ticket=4001,
                    deal_type=FakeMT5.DEAL_TYPE_BALANCE,
                    amount=250.0,
                    time=1_789_588_800,
                    time_msc=1_789_588_800_123,
                ),
            )
        )
    )

    result = reader.read(
        observed_from=START,
        observed_to=END,
    )

    item = result[0]

    assert item.deal_ticket == 4001

    assert (
        item.deal_time_msc
        == 1_789_588_800_123
    )

    assert (
        item.observed_at
        == datetime.fromtimestamp(
            1_789_588_800,
            tz=UTC,
        )
    )


@pytest.mark.parametrize(
    "excluded_type",
    [
        FakeMT5.DEAL_TYPE_BUY,
        FakeMT5.DEAL_TYPE_SELL,
        FakeMT5.DEAL_TYPE_BUY_CANCELED,
        FakeMT5.DEAL_TYPE_SELL_CANCELED,
    ],
)
def test_reader_excludes_trading_and_canceled_trade_deals(
    excluded_type,
):
    reader = MT5AccountCashflowHistoryReader(
        FakeMT5(
            deals=(
                deal(
                    ticket=5001,
                    deal_type=excluded_type,
                    amount=999.0,
                ),
            )
        )
    )

    assert reader.read(
        observed_from=START,
        observed_to=END,
    ) == ()


def test_reader_returns_deterministic_broker_order():
    reader = MT5AccountCashflowHistoryReader(
        FakeMT5(
            deals=(
                deal(
                    ticket=6003,
                    deal_type=FakeMT5.DEAL_TYPE_BALANCE,
                    amount=3.0,
                    time_msc=3000,
                ),
                deal(
                    ticket=6001,
                    deal_type=FakeMT5.DEAL_TYPE_BALANCE,
                    amount=1.0,
                    time_msc=1000,
                ),
                deal(
                    ticket=6002,
                    deal_type=FakeMT5.DEAL_TYPE_BALANCE,
                    amount=2.0,
                    time_msc=2000,
                ),
            )
        )
    )

    result = reader.read(
        observed_from=START,
        observed_to=END,
    )

    assert [
        item.deal_ticket
        for item in result
    ] == [
        6001,
        6002,
        6003,
    ]


def test_reader_reports_mt5_history_failure():
    reader = MT5AccountCashflowHistoryReader(
        FakeMT5(
            fail=True
        )
    )

    with pytest.raises(
        RuntimeError,
        match="history_deals_get failed",
    ):
        reader.read(
            observed_from=START,
            observed_to=END,
        )


def test_reader_requires_timezone_aware_window():
    reader = MT5AccountCashflowHistoryReader(
        FakeMT5()
    )

    with pytest.raises(
        ValueError,
        match="timezone",
    ):
        reader.read(
            observed_from=datetime(
                2026,
                9,
                17,
            ),
            observed_to=END,
        )


def test_reader_rejects_invalid_window_order():
    reader = MT5AccountCashflowHistoryReader(
        FakeMT5()
    )

    with pytest.raises(
        ValueError,
        match="observed_to",
    ):
        reader.read(
            observed_from=END,
            observed_to=START,
        )


def test_evidence_is_immutable():
    reader = MT5AccountCashflowHistoryReader(
        FakeMT5(
            deals=(
                deal(
                    ticket=7001,
                    deal_type=FakeMT5.DEAL_TYPE_BALANCE,
                    amount=100.0,
                ),
            )
        )
    )

    item = reader.read(
        observed_from=START,
        observed_to=END,
    )[0]

    with pytest.raises(
        (
            AttributeError,
            TypeError,
        )
    ):
        item.amount = Decimal("200")


def test_p9a4a_does_not_classify_external_funding():
    reader = MT5AccountCashflowHistoryReader(
        FakeMT5()
    )

    for forbidden in (
        "is_external_deposit",
        "is_external_withdrawal",
        "classify_external_funding",
        "licensed_account_cap_usd",
        "grace_percent",
        "upgrade_required",
        "cycle_id",
        "customer_id",
    ):
        assert not hasattr(
            reader,
            forbidden,
        )
