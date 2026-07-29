import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient

from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)
from backend.trading.execution.execution_mission_acknowledgement_api import (
    create_execution_mission_acknowledgement_router,
)


def create_client():

    store = ExecutionMissionAcknowledgementStore()

    from fastapi import FastAPI

    app = FastAPI()

    app.include_router(
        create_execution_mission_acknowledgement_router(
            store
        )
    )

    return app, store


def test_acknowledge_mission_api():

    app, store = create_client()

    client = TestClient(
        app
    )

    response = client.post(
        "/missions/acknowledge",
        json={
            "mission_id": "mission-001",
            "agent_id": "trusted-agent-001",
            "sequence": 1,
            "status": "ACCEPTED",
            "acknowledged_at": "2026-07-29T00:00:00Z",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "acknowledged"
    assert data["mission_id"] == "mission-001"
    assert store.size() == 1