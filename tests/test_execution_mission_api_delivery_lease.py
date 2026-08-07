from datetime import datetime
from datetime import timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_api import (
    create_execution_mission_router,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)
from backend.trading.execution.execution_mission_delivery_lease_service import (
    ExecutionMissionDeliveryLeaseService,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "secure-secret"

AUTHENTICATION_HEADERS = {
    "X-TODOBA-Agent-ID": AGENT_ID,
    "Authorization": f"Bearer {AGENT_SECRET}",
}


def fixed_clock() -> datetime:
    return datetime(
        2026,
        8,
        7,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id="proof073-mission-001",
        agent_id=AGENT_ID,
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Proof073",
        created_at="2026-08-07T11:59:00Z",
        expires_at="2026-08-07T13:00:00Z",
        sequence=1,
    )


def build_client(
    store: ExecutionMissionStore,
    registry: ExecutionMissionDeliveryLeaseRegistry,
) -> TestClient:
    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    lease_service = ExecutionMissionDeliveryLeaseService(
        registry=registry,
        lease_seconds=30,
        clock=fixed_clock,
    )

    app = FastAPI()

    app.include_router(
        create_execution_mission_router(
            store,
            authenticator,
            lease_service,
        )
    )

    return TestClient(
        app
    )


def test_poll_creates_delivery_lease() -> None:
    store = ExecutionMissionStore()

    registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    store.push(
        build_mission()
    )

    client = build_client(
        store,
        registry,
    )

    response = client.get(
        "/missions/next",
        headers=AUTHENTICATION_HEADERS,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "available"

    assert payload["mission"]["mission_id"] == (
        "proof073-mission-001"
    )

    assert payload["delivery_lease"] == {
        "mission_id": "proof073-mission-001",
        "agent_id": AGENT_ID,
        "leased_at": "2026-08-07T12:00:00Z",
        "expires_at": "2026-08-07T12:00:30Z",
    }

    assert store.size() == 0
    assert registry.size() == 1


def test_poll_lease_belongs_to_authenticated_agent() -> None:
    store = ExecutionMissionStore()

    registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    store.push(
        build_mission()
    )

    client = build_client(
        store,
        registry,
    )

    response = client.get(
        "/missions/next",
        headers=AUTHENTICATION_HEADERS,
    )

    assert response.status_code == 200

    lease = registry.get(
        "proof073-mission-001"
    )

    assert lease is not None

    assert lease.agent_id == AGENT_ID

    assert lease.mission_id == (
        "proof073-mission-001"
    )


def test_empty_poll_does_not_create_delivery_lease() -> None:
    store = ExecutionMissionStore()

    registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    client = build_client(
        store,
        registry,
    )

    response = client.get(
        "/missions/next",
        headers=AUTHENTICATION_HEADERS,
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "empty",
        "mission": None,
    }

    assert registry.size() == 0