from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.execution_mission_completed_api import (
    create_execution_mission_completed_router,
)
from backend.trading.execution.execution_mission_completed_store import (
    ExecutionMissionCompletedStore,
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


def build_client(
    store: ExecutionMissionCompletedStore,
) -> TestClient:
    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    app = FastAPI()

    app.include_router(
        create_execution_mission_completed_router(
            store,
            authenticator,
        )
    )

    return TestClient(
        app
    )


def test_execution_mission_completed_api_receives_evidence() -> None:
    store = ExecutionMissionCompletedStore()
    client = build_client(
        store
    )

    response = client.post(
        "/missions/completed",
        headers=AUTHENTICATION_HEADERS,
        json={
            "mission_id": "completed-001",
            "agent_id": AGENT_ID,
            "sequence": 1,
            "completed_at": "2026-07-31T00:20:00Z",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "completed",
        "mission_id": "completed-001",
        "store_size": 1,
    }

    assert store.size() == 1

    evidence = store.pop()

    assert evidence is not None
    assert evidence.mission_id == (
        "completed-001"
    )


def test_execution_mission_completed_api_rejects_missing_credentials() -> None:
    store = ExecutionMissionCompletedStore()
    client = build_client(
        store
    )

    response = client.post(
        "/missions/completed",
        json={
            "mission_id": "completed-001",
            "agent_id": AGENT_ID,
            "sequence": 1,
            "completed_at": "2026-07-31T00:20:00Z",
        },
    )

    assert response.status_code == 401
    assert store.size() == 0


def test_execution_mission_completed_api_rejects_wrong_agent_identity() -> None:
    store = ExecutionMissionCompletedStore()
    client = build_client(
        store
    )

    response = client.post(
        "/missions/completed",
        headers=AUTHENTICATION_HEADERS,
        json={
            "mission_id": "completed-001",
            "agent_id": "trusted-agent-999",
            "sequence": 1,
            "completed_at": "2026-07-31T00:20:00Z",
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Completion evidence does not belong "
            "to authenticated Agent."
        ),
    }
    assert store.size() == 0