"""
Tests for TODOBA MT5TradeHistoryReader.

These tests use a fake MT5 module.
They do not connect to MetaTrader 5.
"""

from collections import namedtuple

import pytest

from backend.trading.lifecycle.mt5_trade_history_reader import (
    MT5TradeHistoryReader,
)


Deal = namedtuple(
    "Deal",
    [
        "ticket",
        "order",
        "position_id",
        "time",
        "time_msc",
        "type",
        "entry",
        "reason",
        "symbol",
        "volume",
        "price",
        "profit",
        "commission",
        "swap",
        "fee",
        "comment",
    ],
)


class FakeMT5:
    DEAL_ENTRY_IN = 0
    DEAL_ENTRY_OUT = 1
    DEAL_ENTRY_INOUT = 2
    DEAL_ENTRY_OUT_BY = 3

    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1

    DEAL_REASON_CLIENT = 0
    DEAL_REASON_MOBILE = 1
    DEAL_REASON_WEB = 2
    DEAL_REASON_EXPERT = 3
    DEAL_REASON_SL = 4
    DEAL_REASON_TP = 5
    DEAL_REASON_SO = 6

    def __init__(
        self,
        deals=(),
        fail=False,
    ):
        self.deals = deals
        self.fail = fail
        self.requested_position = None

    def history_deals_get(
        self,
        *,
        position,
    ):
        self.requested_position = position

        if self.fail:
            return None

        return self.deals

    def last_error(self):
        return 500, "history unavailable"


def create_entry_deal():
    return Deal(
        ticket=70001,
        order=80001,
        position_id=90001,
        time=1000,
        time_msc=1000000,
        type=FakeMT5.DEAL_TYPE_BUY,
        entry=FakeMT5.DEAL_ENTRY_IN,
        reason=FakeMT5.DEAL_REASON_EXPERT,
        symbol="GOLD.i#",
        volume=0.01,
        price=4105.0,
        profit=0.0,
        commission=-0.25,
        swap=0.0,
        fee=0.0,
        comment="TODOBA",
    )


def create_exit_deal():
    return Deal(
        ticket=70002,
        order=80002,
        position_id=90001,
        time=2000,
        time_msc=2000000,
        type=FakeMT5.DEAL_TYPE_SELL,
        entry=FakeMT5.DEAL_ENTRY_OUT,
        reason=FakeMT5.DEAL_REASON_TP,
        symbol="GOLD.i#",
        volume=0.01,
        price=4125.0,
        profit=20.0,
        commission=-0.50,
        swap=-0.10,
        fee=0.0,
        comment="TODOBA",
    )


def test_reader_returns_closed_trade_observation():
    fake_mt5 = FakeMT5(
        deals=(
            create_entry_deal(),
            create_exit_deal(),
        )
    )

    reader = MT5TradeHistoryReader(
        fake_mt5
    )

    observation = reader.read_closed_position(
        90001
    )

    assert fake_mt5.requested_position == 90001
    assert observation is not None

    assert observation.position_id == 90001
    assert observation.close_deal_id == 70002
    assert observation.order_id == 80002
    assert observation.symbol == "GOLD.i#"

    # A SELL closing deal closed the original BUY position.
    assert observation.action == "BUY"

    assert observation.close_price == 4125.0
    assert observation.gross_profit == 20.0
    assert observation.commission == -0.50
    assert observation.swap == -0.10
    assert observation.net_profit == pytest.approx(
        19.40
    )

    assert observation.close_reason == "take_profit"


def test_reader_returns_none_before_position_closes():
    fake_mt5 = FakeMT5(
        deals=(create_entry_deal(),)
    )

    reader = MT5TradeHistoryReader(
        fake_mt5
    )

    observation = reader.read_closed_position(
        90001
    )

    assert observation is None


def test_reader_reports_mt5_history_failure():
    fake_mt5 = FakeMT5(
        fail=True
    )

    reader = MT5TradeHistoryReader(
        fake_mt5
    )

    with pytest.raises(
        RuntimeError,
        match="history_deals_get failed",
    ):
        reader.read_closed_position(
            90001
        )


def test_reader_rejects_invalid_position_id():
    reader = MT5TradeHistoryReader(
        FakeMT5()
    )

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        reader.read_closed_position(
            0
        )