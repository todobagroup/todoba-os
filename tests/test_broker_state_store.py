"""
TODOBA Broker State Store Tests

Proof:

BrokerState
->
BrokerStateStore
->
latest broker state by account + symbol
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.broker_state import (
    BrokerState,
)
from backend.trading.execution.broker_state_store import (
    BrokerStateStore,
)


def test_store_saves_and_returns_broker_state():
    store = BrokerStateStore()

    state = BrokerState(
        account_fingerprint="demo-account",
        equity=2491.52,
        open_position_count=5,
        symbol="XAUUSD",
        bid=4397.96,
        ask=4398.22,
        spread_points=26.0,
    )

    store.save(
        state
    )

    loaded = store.get(
        account_fingerprint="demo-account",
        symbol="XAUUSD",
    )

    assert loaded == state


def test_store_replaces_previous_state_for_same_account_and_symbol():
    store = BrokerStateStore()

    first = BrokerState(
        account_fingerprint="demo-account",
        equity=2491.52,
        open_position_count=5,
        symbol="XAUUSD",
        bid=4397.96,
        ask=4398.22,
        spread_points=26.0,
    )

    second = BrokerState(
        account_fingerprint="demo-account",
        equity=2600.00,
        open_position_count=4,
        symbol="XAUUSD",
        bid=4400.00,
        ask=4400.20,
        spread_points=20.0,
    )

    store.save(first)
    store.save(second)

    loaded = store.get(
        account_fingerprint="demo-account",
        symbol="XAUUSD",
    )

    assert loaded == second


def test_store_returns_none_for_unknown_state():
    store = BrokerStateStore()

    loaded = store.get(
        account_fingerprint="missing-account",
        symbol="XAUUSD",
    )

    assert loaded is None