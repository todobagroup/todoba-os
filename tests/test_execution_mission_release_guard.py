"""
TODOBA Execution Mission Release Guard Tests

CAP 3I Owner 1 proof:

An authenticated Trusted Agent is eligible to receive
an execution mission only when TODOBA Cloud has current
broker-state evidence for that exact Agent/account binding.

Required rules:

- no Broker State -> DENY
- stale Broker State -> DENY
- Broker State for the wrong bound account -> DENY
- fresh Broker State for the authoritative binding -> READY

This owner does not pop missions, acquire delivery leases,
or mutate mission lifecycle state.
"""

import importlib
from datetime import UTC
from datetime import datetime
from pathlib import Path

import pytest

from backend.trading.execution.broker_state import (
    BrokerState,
)
from backend.trading.execution.broker_state_store import (
    BrokerStateStore,
)
from backend.trading.execution.trusted_agent_account_binding_guard import (
    TrustedAgentAccountBindingGuard,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


AGENT_ID = "trusted-agent-001"
BOUND_ACCOUNT = "broker-a:100001"
OTHER_ACCOUNT = "broker-b:200002"

STATE_RECEIVED_AT = datetime(
    2026,
    8,
    21,
    8,
    0,
    0,
    tzinfo=UTC,
)


def load_release_guard_class():
    module = importlib.import_module(
        "backend.trading.execution."
        "execution_mission_release_guard"
    )

    return module.ExecutionMissionReleaseGuard


def build_broker_state(
    *,
    account_fingerprint: str = BOUND_ACCOUNT,
) -> BrokerState:
    return BrokerState(
        account_fingerprint=account_fingerprint,
        equity=10000.0,
        open_position_count=0,
        pending_order_count=0,
        symbol="XAUUSD",
        bid=4400.0,
        ask=4400.2,
        spread_points=20.0,
    )


def build_binding_guard(
    *,
    tmp_path: Path,
    account_fingerprint: str = BOUND_ACCOUNT,
) -> TrustedAgentAccountBindingGuard:
    binding_store = TrustedAgentAccountBindingStore(
        tmp_path
        / "trusted_agent_account_bindings.json"
    )

    binding_store.initialize_empty()

    binding_store.bind(
        agent_id=AGENT_ID,
        account_fingerprint=account_fingerprint,
    )

    return TrustedAgentAccountBindingGuard(
        binding_store
    )


def build_release_guard(
    *,
    tmp_path: Path,
    broker_state_store: BrokerStateStore,
    now: datetime,
    bound_account: str = BOUND_ACCOUNT,
):
    release_guard_class = (
        load_release_guard_class()
    )

    return release_guard_class(
        broker_state_store=broker_state_store,
        account_binding_guard=(
            build_binding_guard(
                tmp_path=tmp_path,
                account_fingerprint=bound_account,
            )
        ),
        max_age_seconds=30.0,
        clock=lambda: now,
    )


def test_release_guard_denies_agent_without_broker_state(
    tmp_path: Path,
) -> None:
    broker_state_store = BrokerStateStore(
        clock=lambda: STATE_RECEIVED_AT
    )

    guard = build_release_guard(
        tmp_path=tmp_path,
        broker_state_store=broker_state_store,
        now=STATE_RECEIVED_AT,
    )

    with pytest.raises(
        RuntimeError,
        match="Broker state",
    ):
        guard.require_ready(
            agent_id=AGENT_ID
        )


def test_release_guard_denies_stale_broker_state(
    tmp_path: Path,
) -> None:
    broker_state_store = BrokerStateStore(
        clock=lambda: STATE_RECEIVED_AT
    )

    broker_state_store.save(
        build_broker_state(),
        agent_id=AGENT_ID,
    )

    guard = build_release_guard(
        tmp_path=tmp_path,
        broker_state_store=broker_state_store,
        now=datetime(
            2026,
            8,
            21,
            8,
            0,
            31,
            tzinfo=UTC,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="stale",
    ):
        guard.require_ready(
            agent_id=AGENT_ID
        )


def test_release_guard_denies_broker_state_for_wrong_bound_account(
    tmp_path: Path,
) -> None:
    broker_state_store = BrokerStateStore(
        clock=lambda: STATE_RECEIVED_AT
    )

    broker_state_store.save(
        build_broker_state(
            account_fingerprint=OTHER_ACCOUNT
        ),
        agent_id=AGENT_ID,
    )

    guard = build_release_guard(
        tmp_path=tmp_path,
        broker_state_store=broker_state_store,
        now=datetime(
            2026,
            8,
            21,
            8,
            0,
            10,
            tzinfo=UTC,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="binding",
    ):
        guard.require_ready(
            agent_id=AGENT_ID
        )


def test_release_guard_accepts_fresh_broker_state_for_bound_account(
    tmp_path: Path,
) -> None:
    broker_state_store = BrokerStateStore(
        clock=lambda: STATE_RECEIVED_AT
    )

    state = build_broker_state()

    broker_state_store.save(
        state,
        agent_id=AGENT_ID,
    )

    guard = build_release_guard(
        tmp_path=tmp_path,
        broker_state_store=broker_state_store,
        now=datetime(
            2026,
            8,
            21,
            8,
            0,
            10,
            tzinfo=UTC,
        ),
    )

    ready_state = guard.require_ready(
        agent_id=AGENT_ID
    )

    assert ready_state == state
    assert ready_state.account_fingerprint == (
        BOUND_ACCOUNT
    )