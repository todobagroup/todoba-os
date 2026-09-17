"""
P9A1 — Authoritative MT5 Balance Publication

Proof:

MT5 ACCOUNT_BALANCE
->
Trusted Agent broker-state reader
->
authenticated /broker/state
->
BrokerState
->
BrokerStateStore
->
/broker/state/latest

Compatibility:
legacy broker state without balance remains valid.

Commercial safety:
this capability transports broker truth only.
It does not calculate pricing or fall back from balance to equity.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.broker_state import BrokerState
from backend.trading.execution.broker_state_api import (
    create_broker_state_router,
)
from backend.trading.execution.broker_state_store import (
    BrokerStateStore,
)
from backend.trading.execution.executor_authenticator import (
    ExecutorAuthenticator,
)
from backend.trading.execution.trusted_agent_account_binding_guard import (
    TrustedAgentAccountBindingGuard,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


ROOT = Path(__file__).resolve().parents[1]

ACCOUNT_FINGERPRINT = "Broker-Pro:12345678"
AGENT_ID = "trusted-agent-p9a1"
AGENT_SECRET = "p9a1-agent-secret-0123456789abcdef"
EXECUTOR_ID = "executor-p9a1"
EXECUTOR_SECRET = "p9a1-executor-secret-0123456789abcdef"


def _reader_source() -> str:
    return (
        ROOT
        / "MQL5"
        / "Include"
        / "TODOBAExecution"
        / "BrokerStateReader.mqh"
    ).read_text(
        encoding="utf-8",
    )


def _agent_source() -> str:
    return (
        ROOT
        / "MQL5"
        / "Experts"
        / "TODOBA_Trusted_Agent.mq5"
    ).read_text(
        encoding="utf-8",
    )


def _build_client(
    tmp_path: Path,
) -> tuple[TestClient, BrokerStateStore]:

    store = BrokerStateStore()

    binding_store = TrustedAgentAccountBindingStore(
        tmp_path / "trusted_agent_account_bindings.json"
    )

    binding_store.initialize_empty()

    binding_store.bind(
        agent_id=AGENT_ID,
        account_fingerprint=ACCOUNT_FINGERPRINT,
    )

    binding_guard = TrustedAgentAccountBindingGuard(
        binding_store
    )

    agent_authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    executor_authenticator = ExecutorAuthenticator(
        executor_id=EXECUTOR_ID,
        executor_secret=EXECUTOR_SECRET,
    )

    app = FastAPI()

    app.include_router(
        create_broker_state_router(
            store=store,
            authenticator=agent_authenticator,
            executor_authenticator=(
                executor_authenticator
            ),
            account_binding_guard=binding_guard,
        )
    )

    return TestClient(app), store


def _agent_headers() -> dict[str, str]:
    return {
        "X-TODOBA-Agent-ID": AGENT_ID,
        "Authorization": f"Bearer {AGENT_SECRET}",
    }


def _executor_headers() -> dict[str, str]:
    return {
        "X-TODOBA-Executor-ID": EXECUTOR_ID,
        "Authorization": f"Bearer {EXECUTOR_SECRET}",
    }


def _payload(
    *,
    include_balance: bool,
) -> dict[str, object]:

    payload: dict[str, object] = {
        "account_fingerprint": ACCOUNT_FINGERPRINT,
        "equity": 2491.52,
        "open_position_count": 2,
        "pending_order_count": 1,
        "symbol": "XAUUSD",
        "bid": 4400.0,
        "ask": 4400.2,
        "spread_points": 20.0,
        "runtime_environment": "metaquotes_vps",
    }

    if include_balance:
        payload["balance"] = 2400.00

    return payload


def test_mql5_reader_reads_authoritative_account_balance():
    source = _reader_source()

    assert "double balance;" in source

    assert (
        "ACCOUNT_BALANCE"
        in source
    )

    assert (
        "state.balance = balance;"
        in source
    )


def test_trusted_agent_publishes_balance_in_broker_state():
    source = _agent_source()

    start = source.index(
        "void SendBrokerState()"
    )

    end = source.index(
        "void PollCloud()",
        start,
    )

    block = source[start:end]

    assert (
        '"\\"balance\\":"'
        in block
    )

    assert (
        "state.balance"
        in block
    )

    assert (
        '"/broker/state"'
        in block
    )


def test_broker_state_preserves_optional_balance():
    state = BrokerState(
        account_fingerprint=ACCOUNT_FINGERPRINT,
        equity=2491.52,
        open_position_count=2,
        pending_order_count=1,
        symbol="XAUUSD",
        bid=4400.0,
        ask=4400.2,
        spread_points=20.0,
        balance=2400.00,
    )

    assert state.balance == 2400.00


def test_legacy_broker_state_without_balance_remains_valid():
    state = BrokerState(
        account_fingerprint=ACCOUNT_FINGERPRINT,
        equity=2491.52,
        open_position_count=2,
        pending_order_count=1,
        symbol="XAUUSD",
        bid=4400.0,
        ask=4400.2,
        spread_points=20.0,
    )

    assert state.balance is None


def test_authenticated_balance_round_trips_through_broker_state_api(
    tmp_path: Path,
):
    client, store = _build_client(
        tmp_path
    )

    publish = client.post(
        "/broker/state",
        headers=_agent_headers(),
        json=_payload(
            include_balance=True
        ),
    )

    assert publish.status_code == 200

    stored = store.get_for_agent(
        agent_id=AGENT_ID,
    )

    assert stored is not None
    assert stored.balance == 2400.00
    assert stored.equity == 2491.52

    latest = client.get(
        "/broker/state/latest",
        headers=_executor_headers(),
        params={
            "agent_id": AGENT_ID,
        },
    )

    assert latest.status_code == 200
    assert latest.json()["balance"] == 2400.00
    assert latest.json()["equity"] == 2491.52


def test_legacy_publish_without_balance_remains_compatible(
    tmp_path: Path,
):
    client, store = _build_client(
        tmp_path
    )

    publish = client.post(
        "/broker/state",
        headers=_agent_headers(),
        json=_payload(
            include_balance=False
        ),
    )

    assert publish.status_code == 200

    stored = store.get_for_agent(
        agent_id=AGENT_ID,
    )

    assert stored is not None
    assert stored.balance is None

    latest = client.get(
        "/broker/state/latest",
        headers=_executor_headers(),
        params={
            "agent_id": AGENT_ID,
        },
    )

    assert latest.status_code == 200

    body = latest.json()

    assert "balance" not in body
    assert body["equity"] == 2491.52
