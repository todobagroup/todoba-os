from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_api import (
    create_control_mission_router,
)
from backend.trading.control.control_mission_delivery_bridge import (
    ControlMissionDeliveryBridge,
)
from backend.trading.control.control_mission_delivery_expiration_policy import (
    ControlMissionDeliveryExpirationPolicy,
)
from backend.trading.control.control_mission_delivery_lease_persistence import (
    ControlMissionDeliveryLeasePersistence,
)
from backend.trading.control.control_mission_delivery_lease_registry import (
    ControlMissionDeliveryLeaseRegistry,
)
from backend.trading.control.control_mission_delivery_lease_service import (
    ControlMissionDeliveryLeaseService,
)
from backend.trading.control.control_mission_lifecycle_service import (
    ControlMissionLifecycleService,
)
from backend.trading.control.control_mission_persistence import (
    ControlMissionPersistence,
)
from backend.trading.control.control_mission_record_persistence import (
    ControlMissionRecordPersistence,
)
from backend.trading.control.control_mission_registry import (
    ControlMissionRegistry,
)
from backend.trading.control.control_mission_repository import (
    ControlMissionRepository,
)
from backend.trading.control.control_mission_serializer import (
    ControlMissionSerializer,
)
from backend.trading.control.control_mission_service import (
    ControlMissionService,
)
from backend.trading.control.control_mission_signer import (
    ControlMissionSigner,
)
from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
)
from backend.trading.control.control_mission_store import (
    ControlMissionStore,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "proof178-agent-secret"
SIGNING_SECRET = "proof178-control-signing-secret"
MISSION_ID = "control-api-001"

FIXED_NOW = datetime(
    2026,
    8,
    15,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)


def build_mission(
    *,
    agent_id: str = AGENT_ID,
    expires_at: str = "2026-08-15T00:01:00Z",
) -> ControlMission:
    return ControlMission(
        mission_id=MISSION_ID,
        agent_id=agent_id,
        account_fingerprint="account-test",
        action=ControlAction.FLATTEN_ALL,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=5414928751,
        created_at="2026-08-15T00:00:00Z",
        expires_at=expires_at,
        sequence=1,
    )


def agent_headers(
    *,
    secret: str = AGENT_SECRET,
) -> dict[str, str]:
    return {
        "X-TODOBA-Agent-ID": AGENT_ID,
        "Authorization": f"Bearer {secret}",
    }


def build_stack(
    tmp_path: Path,
    *,
    mission: ControlMission | None = None,
    signer: ControlMissionSigner | None = None,
    clock=lambda: FIXED_NOW,
) -> dict:
    repository = ControlMissionRepository()
    mission_persistence = ControlMissionPersistence(
        tmp_path / "control_missions.json"
    )
    registry = ControlMissionRegistry()
    record_persistence = ControlMissionRecordPersistence(
        tmp_path / "control_mission_records.json"
    )
    store = ControlMissionStore()
    bridge = ControlMissionDeliveryBridge(
        store
    )
    lease_registry = ControlMissionDeliveryLeaseRegistry()
    lease_persistence = ControlMissionDeliveryLeasePersistence(
        tmp_path / "control_delivery_leases.json"
    )
    lease_service = ControlMissionDeliveryLeaseService(
        registry=lease_registry,
        lease_seconds=30.0,
        clock=clock,
        persistence=lease_persistence,
    )
    lifecycle_service = ControlMissionLifecycleService(
        registry,
        record_persistence,
        repository=repository,
        mission_persistence=mission_persistence,
        lease_registry=lease_registry,
        lease_persistence=lease_persistence,
    )
    mission_service = ControlMissionService(
        repository,
        mission_persistence,
        bridge,
        registry,
        lifecycle_service,
    )
    active_signer = (
        signer
        if signer is not None
        else ControlMissionSigner(
            SIGNING_SECRET
        )
    )
    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )
    app = FastAPI()
    app.include_router(
        create_control_mission_router(
            store,
            authenticator,
            lease_service,
            lifecycle_service,
            ControlMissionDeliveryExpirationPolicy(),
            active_signer,
        )
    )

    if mission is not None:
        mission_service.create_mission(
            mission
        )

    return {
        "client": TestClient(app),
        "mission": mission,
        "repository": repository,
        "registry": registry,
        "store": store,
        "bridge": bridge,
        "lease_registry": lease_registry,
        "lease_persistence": lease_persistence,
        "signer": active_signer,
    }


def test_agent_receives_signed_leased_control_mission(
    tmp_path: Path,
) -> None:
    mission = build_mission()
    stack = build_stack(
        tmp_path,
        mission=mission,
    )

    response = stack["client"].get(
        "/control/missions/next",
        headers=agent_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "available"
    assert payload["agent_id"] == AGENT_ID
    assert payload["mission_id"] == MISSION_ID
    assert payload["action"] == "FLATTEN_ALL"
    assert payload["mission"]["mission_id"] == MISSION_ID
    assert payload["delivery_lease"] == {
        "mission_id": MISSION_ID,
        "agent_id": AGENT_ID,
        "leased_at": "2026-08-15T00:00:00Z",
        "expires_at": "2026-08-15T00:00:30Z",
    }

    restored_mission = ControlMissionSerializer.deserialize(
        payload["mission"]
    )
    assert stack["signer"].verify(
        restored_mission,
        payload["mission_signature"],
    )
    assert stack["store"].size() == 0
    assert stack["lease_registry"].size() == 1
    record = stack["registry"].get(
        MISSION_ID
    )
    assert record.status is ControlMissionStatus.DELIVERED
    assert record.delivery_attempt_count == 1


def test_agent_receives_empty_response_when_queue_is_empty(
    tmp_path: Path,
) -> None:
    stack = build_stack(
        tmp_path
    )

    response = stack["client"].get(
        "/control/missions/next",
        headers=agent_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "mission": None,
    }


@pytest.mark.parametrize(
    "headers",
    [
        {},
        agent_headers(
            secret="wrong-secret"
        ),
    ],
)
def test_polling_requires_trusted_agent_authentication(
    tmp_path: Path,
    headers: dict[str, str],
) -> None:
    stack = build_stack(
        tmp_path,
        mission=build_mission(),
    )

    response = stack["client"].get(
        "/control/missions/next",
        headers=headers,
    )

    assert response.status_code == 401
    assert stack["store"].size() == 1


def test_polling_does_not_take_another_agent_mission(
    tmp_path: Path,
) -> None:
    stack = build_stack(
        tmp_path,
        mission=build_mission(
            agent_id="trusted-agent-002"
        ),
    )

    response = stack["client"].get(
        "/control/missions/next",
        headers=agent_headers(),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "empty"
    assert stack["store"].size() == 1
    assert stack["lease_registry"].size() == 0


def test_expired_control_mission_is_failed_not_delivered(
    tmp_path: Path,
) -> None:
    stack = build_stack(
        tmp_path,
        mission=build_mission(
            expires_at="2026-08-15T00:00:00Z"
        ),
    )

    response = stack["client"].get(
        "/control/missions/next",
        headers=agent_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "mission": None,
    }
    record = stack["registry"].get(
        MISSION_ID
    )
    assert record.status is ControlMissionStatus.FAILED
    assert record.failure_reason == (
        "Control mission expired before delivery."
    )
    assert stack["repository"].get(
        MISSION_ID
    ) is None
    assert stack["lease_registry"].size() == 0


def test_explicit_redelivery_reuses_lease_and_tracks_attempt(
    tmp_path: Path,
) -> None:
    mission = build_mission()
    stack = build_stack(
        tmp_path,
        mission=mission,
    )

    first = stack["client"].get(
        "/control/missions/next",
        headers=agent_headers(),
    )
    stack["bridge"].redeliver(
        mission
    )
    second = stack["client"].get(
        "/control/missions/next",
        headers=agent_headers(),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["delivery_lease"]
        == second.json()["delivery_lease"]
    )
    assert stack["lease_registry"].size() == 1
    assert stack["registry"].get(
        MISSION_ID
    ).delivery_attempt_count == 2


def test_response_failure_requeues_control_mission(
    tmp_path: Path,
) -> None:
    class FailingSigner(ControlMissionSigner):
        def sign(self, mission) -> str:
            raise RuntimeError(
                "proof signing failure"
            )

    mission = build_mission()
    stack = build_stack(
        tmp_path,
        mission=mission,
        signer=FailingSigner(
            SIGNING_SECRET
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="proof signing failure",
    ):
        stack["client"].get(
            "/control/missions/next",
            headers=agent_headers(),
        )

    assert stack["store"].size() == 1
    assert stack["lease_registry"].size() == 1
    assert stack["registry"].get(
        MISSION_ID
    ).status is ControlMissionStatus.DELIVERED