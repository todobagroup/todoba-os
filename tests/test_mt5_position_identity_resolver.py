"""
Tests for TODOBA MT5PositionIdentityResolver.

These tests use a fake MT5 module.
They do not connect to MetaTrader 5.
"""

from collections import namedtuple

import pytest

from backend.trading.lifecycle.mt5_position_identity_resolver import (
    MT5PositionIdentityResolver,
)
from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)
from backend.trading.lifecycle.trade_status import (
    TradeStatus,
)


Deal = namedtuple(
    "Deal",
    [
        "ticket",
        "position_id",
    ],
)


class FakeMT5:
    def __init__(
        self,
        *,
        deals=(),
        fail=False,
    ):
        self.deals = deals
        self.fail = fail
        self.requested_ticket = None

    def history_deals_get(
        self,
        *,
        ticket,
    ):
        self.requested_ticket = ticket

        if self.fail:
            return None

        return self.deals

    def last_error(self):
        return 500, "history unavailable"


def create_trade_record(
    deal=70001,
) -> TradeRecord:
    return TradeRecord(
        trade_id="TRD-000001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.OPEN,
        order=80001,
        deal=deal,
    )


def test_resolver_returns_position_id_from_deal():
    fake_mt5 = FakeMT5(
        deals=(
            Deal(
                ticket=70001,
                position_id=90001,
            ),
        )
    )

    resolver = MT5PositionIdentityResolver(
        fake_mt5
    )

    position_id = resolver.resolve(
        create_trade_record()
    )

    assert fake_mt5.requested_ticket == 70001
    assert position_id == 90001


def test_resolver_selects_matching_deal():
    fake_mt5 = FakeMT5(
        deals=(
            Deal(
                ticket=70000,
                position_id=90000,
            ),
            Deal(
                ticket=70001,
                position_id=90001,
            ),
        )
    )

    resolver = MT5PositionIdentityResolver(
        fake_mt5
    )

    assert (
        resolver.resolve(
            create_trade_record()
        )
        == 90001
    )


def test_resolver_rejects_record_without_deal():
    resolver = MT5PositionIdentityResolver(
        FakeMT5()
    )

    with pytest.raises(
        ValueError,
        match="no deal ID",
    ):
        resolver.resolve(
            create_trade_record(
                deal=None
            )
        )


def test_resolver_reports_mt5_failure():
    resolver = MT5PositionIdentityResolver(
        FakeMT5(
            fail=True
        )
    )

    with pytest.raises(
        RuntimeError,
        match="history_deals_get failed",
    ):
        resolver.resolve(
            create_trade_record()
        )


def test_resolver_reports_missing_deal():
    resolver = MT5PositionIdentityResolver(
        FakeMT5(
            deals=()
        )
    )

    with pytest.raises(
        LookupError,
        match="No MT5 deal was found",
    ):
        resolver.resolve(
            create_trade_record()
        )


def test_resolver_rejects_invalid_position_id():
    resolver = MT5PositionIdentityResolver(
        FakeMT5(
            deals=(
                Deal(
                    ticket=70001,
                    position_id=0,
                ),
            )
        )
    )

    with pytest.raises(
        LookupError,
        match="no valid position ID",
    ):
        resolver.resolve(
            create_trade_record()
        )


def test_resolver_rejects_invalid_input():
    resolver = MT5PositionIdentityResolver(
        FakeMT5()
    )

    with pytest.raises(
        TypeError,
        match="requires TradeRecord",
    ):
        resolver.resolve(
            "not-a-trade-record"
        )