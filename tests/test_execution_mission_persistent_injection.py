import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.execution_mission_injection_api import (
    create_execution_mission_injection_router,
)

from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)

from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)


def test_persistent_mission_injection_saves_repository(
    tmp_path,
):

    repository = ExecutionMissionRepository()

    persistence = ExecutionMissionPersistence(
        tmp_path / "execution_missions.json"
    )

    app = FastAPI()

    app.include_router(
        create_execution_mission_injection_router(
            repository,
            persistence,
        )
    )

    client = TestClient(app)

    response = client.post(
        "/missions/inject",
        json={
            "mission_id": "persistent-001",
            "agent_id": "trusted-agent-001",
            "account_fingerprint": "demo-account",
            "symbol": "XAUUSD",
            "order_type": "BUY LIMIT",
            "volume": 0.01,
            "entry": 4100.0,
            "sl": 4000.0,
            "tp": 4200.0,
            "magic_number": 10001,
            "comment": "TODOBA Persistent Proof",
            "created_at": "2026-07-29T00:00:00Z",
            "expires_at": "2026-07-30T00:00:00Z",
            "sequence": 1,
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "persisted",
        "mission_id": "persistent-001",
        "repository_size": 1,
    }

    restored_repository = (
        ExecutionMissionRepository()
    )

    restored_count = persistence.restore(
        restored_repository
    )

    assert restored_count == 1

    mission = restored_repository.get(
        "persistent-001"
    )

    assert mission is not None
    assert mission.symbol == "XAUUSD"
    assert mission.order_type == "BUY LIMIT"