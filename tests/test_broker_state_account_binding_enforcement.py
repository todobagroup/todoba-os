"""
TODOBA Broker State Account Binding Enforcement Tests

Proof:

Authenticated Trusted Agent
->
POST /broker/state
->
authoritative Agent/account binding check
->
matching account is accepted

and:

Authenticated Trusted Agent
+
wrong MT5 account
->
403 Forbidden
->
BrokerStateStore remains unchanged
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

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


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "broker-state-binding-secret"

EXECUTOR_ID = "telegram-executor-001"
EXECUTOR_SECRET = "broker-state-executor-secret"

BOUND_ACCOUNT = "account-a"


def build_client(
    tmp_path: Path,
) -> tuple[
    TestClient,
    BrokerStateStore,
]:
    broker_state_store = BrokerStateStore()

    binding_store = TrustedAgentAccountBindingStore(
        tmp_path
        / "trusted_agent_account_bindings.json"
    )

    binding_store.initialize_empty()

    binding_store.bind(
        agent_id=AGENT_ID,
        account_fingerprint=BOUND_ACCOUNT,
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
            store=broker_state_store,
            authenticator=agent_authenticator,
            executor_authenticator=(
                executor_authenticator
            ),
            account_binding_guard=binding_guard,
        )
    )

    return (
        TestClient(app),
        broker_state_store,
    )


def agent_headers() -> dict[str, str]:
    return {
        "X-TODOBA-Agent-ID": AGENT_ID,
        "Authorization": (
            f"Bearer {AGENT_SECRET}"
        ),
    }


def broker_state_payload(
    *,
    account_fingerprint: str,
) -> dict[str, object]:
    return {
        "account_fingerprint": (
            account_fingerprint
        ),
        "equity": 2491.52,
        "open_position_count": 5,
        "pending_order_count": 3,
        "symbol": "XAUUSD",
        "bid": 4397.96,
        "ask": 4398.22,
        "spread_points": 26.0,
    }


def test_matching_bound_account_can_publish(
    tmp_path: Path,
) -> None:
    client, store = build_client(
        tmp_path
    )

    response = client.post(
        "/broker/state",
        headers=agent_headers(),
        json=broker_state_payload(
            account_fingerprint=BOUND_ACCOUNT,
        ),
    )

    assert response.status_code == 200

    stored = store.get(
        account_fingerprint=BOUND_ACCOUNT,
        symbol="XAUUSD",
    )

    assert stored is not None

    assert (
        store.get_for_agent(
            agent_id=AGENT_ID,
        )
        is stored
    )


def test_wrong_bound_account_is_forbidden_without_storage(
    tmp_path: Path,
) -> None:
    client, store = build_client(
        tmp_path
    )

    response = client.post(
        "/broker/state",
        headers=agent_headers(),
        json=broker_state_payload(
            account_fingerprint="account-b",
        ),
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "Trusted Agent account does not match "
            "authoritative binding."
        )
    }

    assert (
        store.get(
            account_fingerprint="account-b",
            symbol="XAUUSD",
        )
        is None
    )

    assert (
        store.get_for_agent(
            agent_id=AGENT_ID,
        )
        is None
    )