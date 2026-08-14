"""
TODOBA Broker State API Tests

Proof:

Trusted Agent
->
POST /broker/state
->
BrokerStateStore
->
authenticated Executor
->
GET /broker/state/latest
"""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.broker_state_api import (
    create_broker_state_router,
)
from backend.trading.execution.broker_state_store import (
    BrokerStateStore,
)
from backend.trading.execution.executor_authenticator import (
    ExecutorAuthenticator,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "proof-broker-state-secret"

EXECUTOR_ID = "telegram-executor-001"
EXECUTOR_SECRET = "proof-executor-secret"


def build_client() -> tuple[
    TestClient,
    BrokerStateStore,
]:
    store = BrokerStateStore()

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
        )
    )

    return TestClient(app), store


def publish_state(
    client: TestClient,
) -> None:
    response = client.post(
        "/broker/state",
        headers={
            "X-TODOBA-Agent-ID": AGENT_ID,
            "Authorization": (
                f"Bearer {AGENT_SECRET}"
            ),
        },
        json={
            "account_fingerprint": "demo-account",
            "equity": 2491.52,
            "open_position_count": 5,
            "pending_order_count": 3,
            "symbol": "XAUUSD",
            "bid": 4397.96,
            "ask": 4398.22,
            "spread_points": 26.0,
        },
    )

    assert response.status_code == 200


def executor_headers() -> dict[str, str]:
    return {
        "X-TODOBA-Executor-ID": EXECUTOR_ID,
        "Authorization": (
            f"Bearer {EXECUTOR_SECRET}"
        ),
    }


def test_authenticated_agent_can_publish_broker_state():
    client, store = build_client()

    publish_state(
        client
    )

    stored = store.get(
        account_fingerprint="demo-account",
        symbol="XAUUSD",
    )

    assert stored is not None
    assert stored.equity == 2491.52
    assert stored.open_position_count == 5
    assert stored.pending_order_count == 3
    assert stored.bid == 4397.96
    assert stored.ask == 4398.22
    assert stored.spread_points == 26.0

    agent_state = store.get_for_agent(
        agent_id=AGENT_ID,
    )

    assert agent_state == stored


def test_authenticated_executor_can_read_latest_agent_state():
    client, _ = build_client()

    publish_state(
        client
    )

    response = client.get(
        "/broker/state/latest",
        headers=executor_headers(),
        params={
            "agent_id": AGENT_ID,
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "available",
        "agent_id": AGENT_ID,
        "account_fingerprint": "demo-account",
        "equity": 2491.52,
        "open_position_count": 5,
        "pending_order_count": 3,
        "symbol": "XAUUSD",
        "bid": 4397.96,
        "ask": 4398.22,
        "spread_points": 26.0,
    }


def test_publish_requires_pending_order_count():
    client, _ = build_client()

    response = client.post(
        "/broker/state",
        headers={
            "X-TODOBA-Agent-ID": AGENT_ID,
            "Authorization": (
                f"Bearer {AGENT_SECRET}"
            ),
        },
        json={
            "account_fingerprint": "demo-account",
            "equity": 2491.52,
            "open_position_count": 5,
            "symbol": "XAUUSD",
            "bid": 4397.96,
            "ask": 4398.22,
            "spread_points": 26.0,
        },
    )

    assert response.status_code == 422


def test_unknown_agent_state_returns_not_found():
    client, _ = build_client()

    response = client.get(
        "/broker/state/latest",
        headers=executor_headers(),
        params={
            "agent_id": "missing-agent",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Broker state not found."
    }