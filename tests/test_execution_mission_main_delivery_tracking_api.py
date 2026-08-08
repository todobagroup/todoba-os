from fastapi.testclient import TestClient

from backend.config import (
    TODOBA_TRUSTED_AGENT_ID,
    TODOBA_TRUSTED_AGENT_SECRET,
)
from backend.main import (
    app,
    execution_mission_delivery_lease_registry,
    execution_mission_delivery_lease_service,
    execution_mission_lifecycle_service,
    execution_mission_registry,
    execution_mission_store,
)
from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


MISSION_ID = "proof075-main-delivery-001"

AUTHENTICATION_HEADERS = {
    "X-TODOBA-Agent-ID": TODOBA_TRUSTED_AGENT_ID,
    "Authorization": (
        f"Bearer {TODOBA_TRUSTED_AGENT_SECRET}"
    ),
}


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id=MISSION_ID,
        agent_id=TODOBA_TRUSTED_AGENT_ID,
        account_fingerprint="proof075-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Proof075 Main Delivery",
        created_at="2026-08-08T09:00:00Z",
        expires_at="2026-08-08T10:00:00Z",
        sequence=1,
    )


def test_main_poll_tracks_mission_delivery(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        execution_mission_delivery_lease_service,
        "persistence",
        None,
    )

    monkeypatch.setattr(
        execution_mission_lifecycle_service,
        "record_persistence",
        None,
    )

    while execution_mission_store.pop_for_agent(
        TODOBA_TRUSTED_AGENT_ID
    ) is not None:
        pass

    execution_mission_delivery_lease_registry.release(
        MISSION_ID
    )

    mission = build_mission()

    execution_mission_registry.register(
        ExecutionMissionRecord(
            mission=mission
        )
    )

    execution_mission_store.push(
        mission
    )

    client = TestClient(
        app
    )

    response = client.get(
        "/missions/next",
        headers=AUTHENTICATION_HEADERS,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "available"

    assert payload["mission"]["mission_id"] == (
        MISSION_ID
    )

    record = execution_mission_registry.get(
        MISSION_ID
    )

    assert record is not None

    assert record.status == (
        ExecutionMissionStatus.DELIVERED
    )

    assert record.delivered_at is not None

    assert record.delivery_attempt_count == 1

    lease = (
        execution_mission_delivery_lease_registry.get(
            MISSION_ID
        )
    )

    assert lease is not None

    assert record.delivered_at == lease.leased_at