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


def build_client(
    store: ExecutionMissionStore,
) -> TestClient:
    app = FastAPI()

    app.include_router(
        create_execution_mission_router(
            store
        )
    )

    return TestClient(
        app
    )


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id="mission-001",
        agent_id="agent-demo-001",
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


def test_next_mission_returns_empty():
    store = ExecutionMissionStore()
    client = build_client(
        store
    )

    response = client.get(
        "/missions/next"
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "mission": None,
    }


def test_next_mission_returns_available():
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

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "available"
    assert payload["mission"]["mission_id"] == (
        "mission-001"
    )
    assert payload["mission"]["agent_id"] == (
        "agent-demo-001"
    )
    assert payload["mission"]["symbol"] == "XAUUSD"
    assert payload["mission"]["order_type"] == "BUY"
    assert payload["mission"]["volume"] == 0.01

    assert store.size() == 0