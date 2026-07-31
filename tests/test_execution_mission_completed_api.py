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


def test_execution_mission_completed_api_receives_evidence():

    store = ExecutionMissionCompletedStore()

    app = FastAPI()

    app.include_router(
        create_execution_mission_completed_router(
            store
        )
    )

    client = TestClient(
        app
    )

    response = client.post(
        "/missions/completed",
        json={
            "mission_id": "completed-001",
            "agent_id": "trusted-agent-001",
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