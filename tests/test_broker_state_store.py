"""
TODOBA Broker State Store Tests

Proof:

Trusted Agent
->
BrokerState
->
BrokerStateStore
->
latest broker state by account + symbol
and by authenticated agent identity
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


def build_state(
    *,
    equity: float = 2491.52,
    open_position_count: int = 5,
    pending_order_count: int = 2,
    bid: float = 4397.96,
    ask: float = 4398.22,
    spread_points: float = 26.0,
) -> BrokerState:
    return BrokerState(
        account_fingerprint="demo-account",
        equity=equity,
        open_position_count=open_position_count,
        pending_order_count=pending_order_count,
        symbol="XAUUSD",
        bid=bid,
        ask=ask,
        spread_points=spread_points,
    )


def test_store_saves_and_returns_broker_state():
    store = BrokerStateStore()

    state = build_state()

    store.save(
        state
    )

    loaded = store.get(
        account_fingerprint="demo-account",
        symbol="XAUUSD",
    )

    assert loaded == state
    assert loaded.pending_order_count == 2


def test_store_replaces_previous_state_for_same_account_and_symbol():
    store = BrokerStateStore()

    first = build_state()

    second = build_state(
        equity=2600.00,
        open_position_count=4,
        pending_order_count=3,
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
    assert loaded.pending_order_count == 3


def test_store_returns_none_for_unknown_state():
    store = BrokerStateStore()

    loaded = store.get(
        account_fingerprint="missing-account",
        symbol="XAUUSD",
    )

    assert loaded is None


def test_store_returns_latest_state_for_authenticated_agent():
    store = BrokerStateStore()

    first = build_state()

    second = build_state(
        equity=2700.00,
        open_position_count=3,
        pending_order_count=4,
        bid=4401.00,
        ask=4401.25,
        spread_points=25.0,
    )

    store.save(
        first,
        agent_id="trusted-agent-001",
    )

    store.save(
        second,
        agent_id="trusted-agent-001",
    )

    loaded = store.get_for_agent(
        agent_id="trusted-agent-001",
    )

    assert loaded == second
    assert loaded.pending_order_count == 4


def test_store_returns_none_for_unknown_agent():
    store = BrokerStateStore()

    loaded = store.get_for_agent(
        agent_id="missing-agent",
    )

    assert loaded is None