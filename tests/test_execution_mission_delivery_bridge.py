from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

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
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "test-trusted-agent-secret"

AUTHENTICATION_HEADERS = {
    "X-TODOBA-Agent-ID": AGENT_ID,
    "Authorization": f"Bearer {AGENT_SECRET}",
}


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id="delivery-001",
        agent_id=AGENT_ID,
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
) -> TestClient:
    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    app = FastAPI()

    app.include_router(
        create_execution_mission_router(
            store,
            authenticator,
        )
    )

    return TestClient(
        app
    )


def test_delivery_store_provides_mission_to_agent() -> None:
    store = ExecutionMissionStore()

    store.push(
        build_mission()
    )

    client = build_client(
        store
    )

    response = client.get(
        "/missions/next",
        headers=AUTHENTICATION_HEADERS,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "available"
    assert payload["mission"]["mission_id"] == (
        "delivery-001"
    )
    assert payload["mission"]["agent_id"] == AGENT_ID
    assert store.size() == 0


def test_delivery_store_rejects_missing_credentials() -> None:
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

    assert response.status_code == 401
    assert store.size() == 1