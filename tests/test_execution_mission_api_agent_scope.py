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


AGENT_ID = "trusted-agent-b"
AGENT_SECRET = "secure-secret"

AUTHENTICATION_HEADERS = {
    "X-TODOBA-Agent-ID": AGENT_ID,
    "Authorization": f"Bearer {AGENT_SECRET}",
}


def build_mission(
    mission_id: str,
    agent_id: str,
) -> ExecutionMission:
    return ExecutionMission(
        mission_id=mission_id,
        agent_id=agent_id,
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA API Agent Scope Test",
        created_at="2026-08-04T00:00:00Z",
        expires_at="2026-08-05T00:00:00Z",
        sequence=1,
    )


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


def test_api_returns_only_requested_agent_mission() -> None:
    store = ExecutionMissionStore()

    store.push(
        build_mission(
            "mission-agent-a",
            "trusted-agent-a",
        )
    )

    store.push(
        build_mission(
            "mission-agent-b",
            AGENT_ID,
        )
    )

    client = build_client(
        store
    )

    response = client.get(
        f"/missions/next?agent_id={AGENT_ID}",
        headers=AUTHENTICATION_HEADERS,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["mission"]["agent_id"] == AGENT_ID
    assert store.size() == 1


def test_api_rejects_missing_credentials() -> None:
    store = ExecutionMissionStore()

    store.push(
        build_mission(
            "mission-agent-b",
            AGENT_ID,
        )
    )

    client = build_client(
        store
    )

    response = client.get(
        f"/missions/next?agent_id={AGENT_ID}"
    )

    assert response.status_code == 401
    assert store.size() == 1


def test_store_consumes_mission_once() -> None:
    store = ExecutionMissionStore()

    mission = build_mission(
        "mission-single-use",
        "trusted-agent-a",
    )

    store.push(
        mission
    )

    first = store.pop_for_agent(
        "trusted-agent-a"
    )

    second = store.pop_for_agent(
        "trusted-agent-a"
    )

    assert first is mission
    assert second is None
    assert store.size() == 0