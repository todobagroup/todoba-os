from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from fastapi import FastAPI
from fastapi.testclient import TestClient


from backend.trading.execution.execution_mission_failed_api import (
    create_execution_mission_failed_router,
)

from backend.trading.execution.execution_mission_failed_store import (
    ExecutionMissionFailedStore,
)


def test_execution_mission_failed_api_receives_evidence():

    store = ExecutionMissionFailedStore()

    app = FastAPI()

    app.include_router(
        create_execution_mission_failed_router(
            store
        )
    )

    client = TestClient(
        app
    )

    response = client.post(
        "/missions/failed",
        json={
            "mission_id": "failed-001",
            "agent_id": "trusted-agent-001",
            "sequence": 1,
            "failed_at": "2026-07-31T00:30:00Z",
            "failure_reason": "broker_rejected_order",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "failed",
        "mission_id": "failed-001",
        "store_size": 1,
    }

    assert store.size() == 1

    evidence = store.pop()

    assert evidence is not None

    assert evidence.mission_id == (
        "failed-001"
    )

    assert evidence.failure_reason == (
        "broker_rejected_order"
    )