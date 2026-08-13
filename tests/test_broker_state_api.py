"""
TODOBA Broker State API Tests

Proof:

Trusted Agent
->
POST /broker/state
->
Agent authentication
->
BrokerState
->
BrokerStateStore
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
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


def test_authenticated_agent_can_publish_broker_state():
    store = BrokerStateStore()

    authenticator = TrustedAgentAuthenticator(
        agent_id="trusted-agent-001",
        agent_secret="proof-broker-state-secret",
    )

    app = FastAPI()

    app.include_router(
        create_broker_state_router(
            store=store,
            authenticator=authenticator,
        )
    )

    client = TestClient(app)

    response = client.post(
        "/broker/state",
        headers={
            "X-TODOBA-Agent-ID": (
                "trusted-agent-001"
            ),
            "Authorization": (
                "Bearer proof-broker-state-secret"
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

    assert response.status_code == 200

    assert response.json() == {
        "status": "stored",
        "account_fingerprint": "demo-account",
        "symbol": "XAUUSD",
    }

    stored = store.get(
        account_fingerprint="demo-account",
        symbol="XAUUSD",
    )

    assert stored is not None
    assert stored.equity == 2491.52
    assert stored.open_position_count == 5
    assert stored.bid == 4397.96
    assert stored.ask == 4398.22
    assert stored.spread_points == 26.0