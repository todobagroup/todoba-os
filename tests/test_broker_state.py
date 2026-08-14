"""
TODOBA Broker State Tests

Proof:

Trusted Agent broker/account facts
->
BrokerState contract
->
TODOBA Cloud decision inputs
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.broker_state import (
    BrokerState,
)


def test_broker_state_preserves_remote_account_and_market_facts():
    state = BrokerState(
        account_fingerprint="demo-account",
        equity=2491.52,
        open_position_count=5,
        pending_order_count=3,
        symbol="XAUUSD",
        bid=4397.96,
        ask=4398.22,
        spread_points=26.0,
    )

    assert state.account_fingerprint == (
        "demo-account"
    )

    assert state.equity == 2491.52
    assert state.open_position_count == 5
    assert state.pending_order_count == 3

    assert state.symbol == "XAUUSD"

    assert state.bid == 4397.96
    assert state.ask == 4398.22

    assert state.spread_points == 26.0


def test_broker_state_rejects_invalid_equity():
    try:
        BrokerState(
            account_fingerprint="demo-account",
            equity=0.0,
            open_position_count=0,
            pending_order_count=0,
            symbol="XAUUSD",
            bid=4397.96,
            ask=4398.22,
            spread_points=26.0,
        )

    except ValueError as error:
        assert str(error) == (
            "equity must be greater than zero."
        )

    else:
        raise AssertionError(
            "BrokerState must reject invalid equity."
        )


def test_broker_state_rejects_negative_position_count():
    try:
        BrokerState(
            account_fingerprint="demo-account",
            equity=2491.52,
            open_position_count=-1,
            pending_order_count=0,
            symbol="XAUUSD",
            bid=4397.96,
            ask=4398.22,
            spread_points=26.0,
        )

    except ValueError as error:
        assert str(error) == (
            "open_position_count cannot be negative."
        )

    else:
        raise AssertionError(
            "BrokerState must reject negative "
            "open_position_count."
        )


def test_broker_state_rejects_negative_pending_order_count():
    try:
        BrokerState(
            account_fingerprint="demo-account",
            equity=2491.52,
            open_position_count=0,
            pending_order_count=-1,
            symbol="XAUUSD",
            bid=4397.96,
            ask=4398.22,
            spread_points=26.0,
        )

    except ValueError as error:
        assert str(error) == (
            "pending_order_count cannot be negative."
        )

    else:
        raise AssertionError(
            "BrokerState must reject negative "
            "pending_order_count."
        )