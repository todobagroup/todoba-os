from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.execution_mission_injection_api import (
    create_execution_mission_injection_router,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)


def test_inject_mission_pushes_into_store():
    store = ExecutionMissionStore()

    app = FastAPI()
    app.include_router(
        create_execution_mission_injection_router(
            store
        )
    )

    client = TestClient(app)

    response = client.post(
        "/missions/inject",
        json={
            "mission_id": "proof-001",
            "agent_id": "trusted-agent-001",
            "account_fingerprint": "demo-account",
            "symbol": "XAUUSD",
            "order_type": "BUY",
            "volume": 0.01,
            "entry": None,
            "sl": 4000.0,
            "tp": 4200.0,
            "magic_number": 10001,
            "comment": "TODOBA Proof 001",
            "created_at": "2026-07-28T00:00:00Z",
            "expires_at": "2026-07-29T00:00:00Z",
            "sequence": 1,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "queued",
        "mission_id": "proof-001",
        "queue_size": 1,
    }

    assert store.size() == 1

    mission = store.pop()

    assert mission is not None
    assert mission.mission_id == "proof-001"
    assert mission.agent_id == "trusted-agent-001"
    assert mission.symbol == "XAUUSD"
    assert mission.order_type == "BUY"
    assert mission.volume == 0.01