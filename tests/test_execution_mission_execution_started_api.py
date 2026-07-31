from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from fastapi import FastAPI
from fastapi.testclient import TestClient


from backend.trading.execution.execution_mission_execution_started_api import (
    create_execution_mission_execution_started_router,
)

from backend.trading.execution.execution_mission_execution_started_store import (
    ExecutionMissionExecutionStartedStore,
)


def test_execution_started_api_receives_evidence():

    store = ExecutionMissionExecutionStartedStore()

    app = FastAPI()

    app.include_router(
        create_execution_mission_execution_started_router(
            store
        )
    )

    client = TestClient(
        app
    )

    response = client.post(
        "/missions/execution_started",
        json={
            "mission_id": "execution-started-001",
            "agent_id": "trusted-agent-001",
            "sequence": 1,
            "started_at": "2026-07-31T00:10:00Z",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "execution_started",
        "mission_id": "execution-started-001",
        "store_size": 1,
    }

    assert store.size() == 1

    evidence = store.pop()

    assert evidence is not None

    assert evidence.mission_id == (
        "execution-started-001"
    )