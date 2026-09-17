"""
P9A4A3 ? MT5 Account Cashflow Source Identity Binding.

Cashflow evidence must carry the canonical MT5 account
fingerprint observed from the same MT5 session that supplies
deal history.

This capability does NOT classify external funding.
"""

from collections import namedtuple
from datetime import UTC
from datetime import datetime

from backend.trading.lifecycle.mt5_account_cashflow_history_reader import (
    MT5AccountCashflowHistoryReader,
)


Account = namedtuple(
    "Account",
    (
        "login",
        "server",
    ),
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

    def account_info(self):
        return Account(
            login=68353796,
            server="RoboForex-Pro",
        )

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


def test_cashflow_evidence_carries_canonical_account_fingerprint():
    evidence = MT5AccountCashflowHistoryReader(
        FakeMT5()
    ).read(
        observed_from=START,
        observed_to=END,
    )

    assert len(evidence) == 1

    assert (
        evidence[0].account_fingerprint
        == "RoboForex-Pro:68353796"
    )


def test_account_identity_failure_fails_closed():
    class MissingAccountMT5(FakeMT5):
        def account_info(self):
            return None

    reader = MT5AccountCashflowHistoryReader(
        MissingAccountMT5()
    )

    try:
        reader.read(
            observed_from=START,
            observed_to=END,
        )
    except RuntimeError as exc:
        assert "account" in str(exc).lower()
    else:
        raise AssertionError(
            "Missing authoritative MT5 account identity "
            "must fail closed."
        )


def test_source_identity_binding_does_not_classify_funding():
    evidence = MT5AccountCashflowHistoryReader(
        FakeMT5()
    ).read(
        observed_from=START,
        observed_to=END,
    )[0]

    assert (
        evidence.account_fingerprint
        == "RoboForex-Pro:68353796"
    )

    for forbidden in (
        "is_external_deposit",
        "is_external_withdrawal",
        "funding_direction",
        "customer_funding_kind",
        "customer_id",
        "cycle_id",
        "upgrade_required",
    ):
        assert not hasattr(
            evidence,
            forbidden,
        )
