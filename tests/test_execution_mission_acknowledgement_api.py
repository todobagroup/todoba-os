import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.execution_mission_acknowledgement_api import (
    create_execution_mission_acknowledgement_router,
)
from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "test-trusted-agent-secret"

AUTHENTICATION_HEADERS = {
    "X-TODOBA-Agent-ID": AGENT_ID,
    "Authorization": f"Bearer {AGENT_SECRET}",
}


def create_client() -> tuple[
    TestClient,
    ExecutionMissionAcknowledgementStore,
]:
    store = ExecutionMissionAcknowledgementStore()

    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    app = FastAPI()

    app.include_router(
        create_execution_mission_acknowledgement_router(
            store,
            authenticator,
        )
    )

    return TestClient(app), store


def build_payload(
    agent_id: str = AGENT_ID,
) -> dict[str, object]:
    return {
        "mission_id": "mission-001",
        "agent_id": agent_id,
        "sequence": 1,
        "status": "ACCEPTED",
        "acknowledged_at": "2026-07-29T00:00:00Z",
    }


def test_acknowledge_mission_api() -> None:
    client, store = create_client()

    response = client.post(
        "/missions/acknowledge",
        headers=AUTHENTICATION_HEADERS,
        json=build_payload(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "acknowledged",
        "mission_id": "mission-001",
        "store_size": 1,
    }
    assert store.size() == 1


def test_acknowledge_mission_api_rejects_missing_credentials() -> None:
    client, store = create_client()

    response = client.post(
        "/missions/acknowledge",
        json=build_payload(),
    )

    assert response.status_code == 401
    assert store.size() == 0


def test_acknowledge_mission_api_rejects_wrong_agent_identity() -> None:
    client, store = create_client()

    response = client.post(
        "/missions/acknowledge",
        headers=AUTHENTICATION_HEADERS,
        json=build_payload(
            agent_id="trusted-agent-999"
        ),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Acknowledgement evidence does not belong "
            "to authenticated Agent."
        ),
    }
    assert store.size() == 0