import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_delivery_lease import (
    ControlMissionDeliveryLease,
)
from backend.trading.control.control_mission_delivery_lease_registry import (
    ControlMissionDeliveryLeaseRegistry,
)
from backend.trading.control.control_mission_lifecycle_api import (
    create_control_mission_lifecycle_router,
)
from backend.trading.control.control_mission_lifecycle_service import (
    ControlMissionLifecycleService,
)
from backend.trading.control.control_mission_record import (
    ControlMissionRecord,
)
from backend.trading.control.control_mission_registry import (
    ControlMissionRegistry,
)
from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


AGENT_ID = "trusted-agent-001"
OTHER_AGENT_ID = "trusted-agent-002"
AGENT_SECRET = "test-trusted-agent-secret"
MISSION_ID = "control-lifecycle-api-001"

AUTHENTICATION_HEADERS = {
    "X-TODOBA-Agent-ID": AGENT_ID,
    "Authorization": f"Bearer {AGENT_SECRET}",
}


def build_mission(
    *,
    agent_id: str = AGENT_ID,
) -> ControlMission:
    return ControlMission(
        mission_id=MISSION_ID,
        agent_id=agent_id,
        account_fingerprint="demo-account",
        action=ControlAction.CLOSE_GREEN,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=5414928751,
        created_at="2026-08-15T00:00:00Z",
        expires_at="2026-08-15T00:01:00Z",
        sequence=1,
    )


def create_client(
    *,
    status_value: ControlMissionStatus = (
        ControlMissionStatus.DELIVERED
    ),
    mission_agent_id: str = AGENT_ID,
    register_mission: bool = True,
    with_lease: bool = True,
) -> tuple[
    TestClient,
    ControlMissionRegistry,
    ControlMissionDeliveryLeaseRegistry,
]:
    registry = ControlMissionRegistry()
    lease_registry = (
        ControlMissionDeliveryLeaseRegistry()
    )

    if register_mission:
        registry.register(
            ControlMissionRecord(
                mission=build_mission(
                    agent_id=mission_agent_id
                ),
                status=status_value,
            )
        )

    if with_lease and register_mission:
        lease_registry.acquire(
            ControlMissionDeliveryLease(
                mission_id=MISSION_ID,
                agent_id=mission_agent_id,
                leased_at="2026-08-15T00:00:05Z",
                expires_at="2026-08-15T00:00:35Z",
            )
        )

    lifecycle_service = (
        ControlMissionLifecycleService(
            registry,
            lease_registry=lease_registry,
        )
    )

    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    app = FastAPI()
    app.include_router(
        create_control_mission_lifecycle_router(
            lifecycle_service,
            authenticator,
        )
    )

    return (
        TestClient(app),
        registry,
        lease_registry,
    )


def acknowledgement_payload(
    *,
    agent_id: str = AGENT_ID,
) -> dict[str, object]:
    return {
        "mission_id": MISSION_ID,
        "agent_id": agent_id,
        "acknowledged_at": "2026-08-15T00:00:10Z",
    }


def started_payload() -> dict[str, object]:
    return {
        "mission_id": MISSION_ID,
        "agent_id": AGENT_ID,
        "started_at": "2026-08-15T00:00:11Z",
    }


def completed_payload() -> dict[str, object]:
    return {
        "mission_id": MISSION_ID,
        "agent_id": AGENT_ID,
        "completed_at": "2026-08-15T00:00:12Z",
        "matched_position_count": 3,
        "closed_position_count": 3,
        "matched_pending_order_count": 0,
        "canceled_pending_order_count": 0,
    }


def failed_payload() -> dict[str, object]:
    return {
        "mission_id": MISSION_ID,
        "agent_id": AGENT_ID,
        "failed_at": "2026-08-15T00:00:12Z",
        "failure_reason": "One position could not close.",
        "matched_position_count": 3,
        "closed_position_count": 2,
        "matched_pending_order_count": 0,
        "canceled_pending_order_count": 0,
        "failed_item_count": 1,
    }


def acknowledge_and_start(
    client: TestClient,
) -> None:
    acknowledgement = client.post(
        "/control/missions/acknowledge",
        headers=AUTHENTICATION_HEADERS,
        json=acknowledgement_payload(),
    )

    assert acknowledgement.status_code == 200

    started = client.post(
        "/control/missions/execution-started",
        headers=AUTHENTICATION_HEADERS,
        json=started_payload(),
    )

    assert started.status_code == 200


def test_control_mission_full_success_lifecycle() -> None:
    client, registry, lease_registry = create_client()

    acknowledgement = client.post(
        "/control/missions/acknowledge",
        headers=AUTHENTICATION_HEADERS,
        json=acknowledgement_payload(),
    )

    assert acknowledgement.status_code == 200
    assert acknowledgement.json() == {
        "status": "acknowledged",
        "mission_id": MISSION_ID,
    }
    assert lease_registry.get(
        MISSION_ID
    ) is None

    started = client.post(
        "/control/missions/execution-started",
        headers=AUTHENTICATION_HEADERS,
        json=started_payload(),
    )

    assert started.status_code == 200
    assert started.json() == {
        "status": "executing",
        "mission_id": MISSION_ID,
    }

    completed = client.post(
        "/control/missions/completed",
        headers=AUTHENTICATION_HEADERS,
        json=completed_payload(),
    )

    assert completed.status_code == 200
    assert completed.json() == {
        "status": "completed",
        "mission_id": MISSION_ID,
    }

    record = registry.get(
        MISSION_ID
    )

    assert record is not None
    assert record.status is ControlMissionStatus.COMPLETED
    assert record.matched_position_count == 3
    assert record.closed_position_count == 3
    assert record.matched_pending_order_count == 0
    assert record.canceled_pending_order_count == 0


def test_control_mission_failure_records_partial_result() -> None:
    client, registry, _ = create_client()

    acknowledge_and_start(
        client
    )

    response = client.post(
        "/control/missions/failed",
        headers=AUTHENTICATION_HEADERS,
        json=failed_payload(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "failed",
        "mission_id": MISSION_ID,
    }

    record = registry.get(
        MISSION_ID
    )

    assert record is not None
    assert record.status is ControlMissionStatus.FAILED
    assert record.failure_reason == (
        "One position could not close."
    )
    assert record.matched_position_count == 3
    assert record.closed_position_count == 2
    assert record.failed_item_count == 1


def test_repeated_acknowledgement_is_idempotent() -> None:
    client, registry, _ = create_client()

    first = client.post(
        "/control/missions/acknowledge",
        headers=AUTHENTICATION_HEADERS,
        json=acknowledgement_payload(),
    )
    second = client.post(
        "/control/missions/acknowledge",
        headers=AUTHENTICATION_HEADERS,
        json=acknowledgement_payload(),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert registry.get(
        MISSION_ID
    ).status is ControlMissionStatus.ACKNOWLEDGED


def test_repeated_completion_is_idempotent() -> None:
    client, registry, _ = create_client()

    acknowledge_and_start(
        client
    )

    first = client.post(
        "/control/missions/completed",
        headers=AUTHENTICATION_HEADERS,
        json=completed_payload(),
    )
    second = client.post(
        "/control/missions/completed",
        headers=AUTHENTICATION_HEADERS,
        json=completed_payload(),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert registry.get(
        MISSION_ID
    ).status is ControlMissionStatus.COMPLETED


def test_lifecycle_api_rejects_missing_credentials() -> None:
    client, registry, _ = create_client()

    response = client.post(
        "/control/missions/acknowledge",
        json=acknowledgement_payload(),
    )

    assert response.status_code == 401
    assert registry.get(
        MISSION_ID
    ).status is ControlMissionStatus.DELIVERED


def test_lifecycle_api_rejects_wrong_secret() -> None:
    client, registry, _ = create_client()

    response = client.post(
        "/control/missions/acknowledge",
        headers={
            "X-TODOBA-Agent-ID": AGENT_ID,
            "Authorization": "Bearer wrong-secret",
        },
        json=acknowledgement_payload(),
    )

    assert response.status_code == 401
    assert registry.get(
        MISSION_ID
    ).status is ControlMissionStatus.DELIVERED


def test_lifecycle_api_rejects_evidence_agent_mismatch() -> None:
    client, registry, _ = create_client()

    response = client.post(
        "/control/missions/acknowledge",
        headers=AUTHENTICATION_HEADERS,
        json=acknowledgement_payload(
            agent_id=OTHER_AGENT_ID
        ),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Control mission evidence does not belong "
            "to authenticated Agent."
        ),
    }
    assert registry.get(
        MISSION_ID
    ).status is ControlMissionStatus.DELIVERED


def test_lifecycle_api_rejects_mission_owner_mismatch() -> None:
    client, registry, _ = create_client(
        mission_agent_id=OTHER_AGENT_ID
    )

    response = client.post(
        "/control/missions/acknowledge",
        headers=AUTHENTICATION_HEADERS,
        json=acknowledgement_payload(),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Control mission does not belong to "
            "authenticated Agent."
        ),
    }
    assert registry.get(
        MISSION_ID
    ).status is ControlMissionStatus.DELIVERED


def test_lifecycle_api_returns_not_found_for_unknown_mission() -> None:
    client, _, _ = create_client(
        register_mission=False,
        with_lease=False,
    )

    response = client.post(
        "/control/missions/acknowledge",
        headers=AUTHENTICATION_HEADERS,
        json=acknowledgement_payload(),
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Control mission record not found.",
    }


def test_lifecycle_api_maps_invalid_transition_to_conflict() -> None:
    client, registry, _ = create_client(
        status_value=ControlMissionStatus.CREATED,
        with_lease=False,
    )

    response = client.post(
        "/control/missions/acknowledge",
        headers=AUTHENTICATION_HEADERS,
        json=acknowledgement_payload(),
    )

    assert response.status_code == 409
    assert registry.get(
        MISSION_ID
    ).status is ControlMissionStatus.CREATED


@pytest.mark.parametrize(
    "field_name,invalid_value",
    [
        ("matched_position_count", -1),
        ("closed_position_count", True),
        ("matched_pending_order_count", -1),
        ("canceled_pending_order_count", False),
    ],
)
def test_completed_api_rejects_invalid_counts(
    field_name: str,
    invalid_value: object,
) -> None:
    client, registry, _ = create_client()
    acknowledge_and_start(
        client
    )

    payload = completed_payload()
    payload[field_name] = invalid_value

    response = client.post(
        "/control/missions/completed",
        headers=AUTHENTICATION_HEADERS,
        json=payload,
    )

    assert response.status_code == 422
    assert registry.get(
        MISSION_ID
    ).status is ControlMissionStatus.EXECUTING


def test_completed_api_rejects_partial_success_counts() -> None:
    client, registry, _ = create_client()
    acknowledge_and_start(
        client
    )

    payload = completed_payload()
    payload["closed_position_count"] = 2

    response = client.post(
        "/control/missions/completed",
        headers=AUTHENTICATION_HEADERS,
        json=payload,
    )

    assert response.status_code == 409
    assert registry.get(
        MISSION_ID
    ).status is ControlMissionStatus.EXECUTING


def test_failed_api_rejects_empty_failure_reason() -> None:
    client, registry, _ = create_client()
    acknowledge_and_start(
        client
    )

    payload = failed_payload()
    payload["failure_reason"] = ""

    response = client.post(
        "/control/missions/failed",
        headers=AUTHENTICATION_HEADERS,
        json=payload,
    )

    assert response.status_code == 422
    assert registry.get(
        MISSION_ID
    ).status is ControlMissionStatus.EXECUTING


def test_router_rejects_wrong_dependencies() -> None:
    registry = ControlMissionRegistry()
    lifecycle_service = ControlMissionLifecycleService(
        registry
    )
    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    with pytest.raises(
        TypeError,
        match="requires ControlMissionLifecycleService",
    ):
        create_control_mission_lifecycle_router(
            "not-a-lifecycle-service",
            authenticator,
        )

    with pytest.raises(
        TypeError,
        match="requires TrustedAgentAuthenticator",
    ):
        create_control_mission_lifecycle_router(
            lifecycle_service,
            "not-an-authenticator",
        )