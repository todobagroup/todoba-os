from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_api import (
    create_execution_mission_router,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


AGENT_ID = "agent-demo-001"
AGENT_SECRET = "secure-secret"

AUTHENTICATION_HEADERS = {
    "X-TODOBA-Agent-ID": AGENT_ID,
    "Authorization": f"Bearer {AGENT_SECRET}",
}


def build_client(
    store: ExecutionMissionStore,
) -> TestClient:
    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    app = FastAPI()

    app.include_router(
        create_execution_mission_router(
            store,
            authenticator,
        )
    )

    return TestClient(
        app
    )


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id="mission-001",
        agent_id=AGENT_ID,
        account_fingerprint="demo-account-001",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4120.0,
        magic_number=10001,
        comment="TODOBA",
        created_at="2026-07-28T00:00:00Z",
        expires_at="2026-07-28T00:01:00Z",
        sequence=1,
    )


def test_next_mission_returns_empty() -> None:
    store = ExecutionMissionStore()
    client = build_client(
        store
    )

    response = client.get(
        "/missions/next",
        headers=AUTHENTICATION_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "mission": None,
    }


def test_next_mission_returns_available() -> None:
    store = ExecutionMissionStore()
    store.push(
        build_mission()
    )

    client = build_client(
        store
    )

    response = client.get(
        "/missions/next",
        headers=AUTHENTICATION_HEADERS,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "available"
    assert payload["mission"]["mission_id"] == (
        "mission-001"
    )
    assert payload["mission"]["agent_id"] == AGENT_ID
    assert payload["mission"]["symbol"] == "XAUUSD"
    assert payload["mission"]["order_type"] == "BUY"
    assert payload["mission"]["volume"] == 0.01

    assert store.size() == 0


def test_next_mission_rejects_missing_credentials() -> None:
    store = ExecutionMissionStore()
    store.push(
        build_mission()
    )

    client = build_client(
        store
    )

    response = client.get(
        "/missions/next"
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Trusted Agent authentication failed.",
    }

    assert store.size() == 1