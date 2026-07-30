from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.execution_mission_api import (
    create_execution_mission_router,
)

from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id="delivery-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Delivery Proof",
        created_at="2026-07-29T00:00:00Z",
        expires_at="2026-07-30T00:00:00Z",
        sequence=1,
    )


def build_client(
    store: ExecutionMissionStore,
):
    app = FastAPI()

    app.include_router(
        create_execution_mission_router(
            store
        )
    )

    return TestClient(app)


def test_delivery_store_provides_mission_to_agent():

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

    assert (
        payload["mission"]["mission_id"]
        == "delivery-001"
    )

    assert (
        payload["mission"]["agent_id"]
        == "trusted-agent-001"
    )

    assert store.size() == 0