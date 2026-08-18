from datetime import datetime
from datetime import timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
)

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_api import (
    create_control_mission_router,
)
from backend.trading.control.control_mission_delivery_expiration_policy import (
    ControlMissionDeliveryExpirationPolicy,
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
from backend.trading.control.control_mission_record import (
    ControlMissionRecord,
)
from backend.trading.control.control_mission_registry import (
    ControlMissionRegistry,
)
from backend.trading.control.control_mission_serializer import (
    ControlMissionSerializer,
)
from backend.trading.control.control_mission_serializer_v2 import (
    ControlMissionSerializerV2,
)
from backend.trading.control.control_mission_signer import (
    ControlMissionSigner,
)
from backend.trading.control.control_mission_signer_v2 import (
    ControlMissionSignerV2,
)
from backend.trading.control.control_mission_store import (
    ControlMissionStore,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "proof-control-protocol-agent-secret"
SIGNING_SECRET = "proof-control-protocol-signing-secret"

MISSION_ID = "control-protocol-001"
SECURITY_SEQUENCE = 42

FIXED_NOW = datetime(
    2026,
    8,
    18,
    12,
    0,
    0,
    tzinfo=timezone.utc,
)


def build_mission() -> ControlMission:
    return ControlMission(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        account_fingerprint="demo-account",
        action=ControlAction.FLATTEN_ALL,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=168,
        created_at="2026-08-18T11:59:00Z",
        expires_at="2026-08-18T13:00:00Z",
        sequence=168002,
        security_sequence=SECURITY_SEQUENCE,
    )


def authentication_headers(
    *,
    protocol: str | None = None,
) -> dict[str, str]:
    headers = {
        "X-TODOBA-Agent-ID": AGENT_ID,
        "Authorization": (
            f"Bearer {AGENT_SECRET}"
        ),
    }

    if protocol is not None:
        headers[
            "X-TODOBA-Mission-Protocol"
        ] = protocol

    return headers


def build_client(
    tmp_path: Path,
    store: ControlMissionStore,
    *,
    enable_v2: bool = False,
) -> TestClient:
    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    lease_registry = (
        ControlMissionDeliveryLeaseRegistry()
    )

    lease_service = (
        ControlMissionDeliveryLeaseService(
            registry=lease_registry,
            lease_seconds=30.0,
            clock=lambda: FIXED_NOW,
        )
    )

    mission_registry = (
        ControlMissionRegistry()
    )

    mission_registry.register(
        ControlMissionRecord(
           mission=build_mission(),
           status=ControlMissionStatus.QUEUED,
        )
    )

    lifecycle_service = (
        ControlMissionLifecycleService(
            mission_registry
        )
    )

    signer_v1 = ControlMissionSigner(
        SIGNING_SECRET
    )

    app = FastAPI()

    if enable_v2:
        signer_v2 = ControlMissionSignerV2(
            SIGNING_SECRET
        )

        app.include_router(
            create_control_mission_router(
                store,
                authenticator,
                lease_service,
                lifecycle_service,
                ControlMissionDeliveryExpirationPolicy(),
                signer_v1,
                signer_v2=signer_v2,
            )
        )
    else:
        app.include_router(
            create_control_mission_router(
                store,
                authenticator,
                lease_service,
                lifecycle_service,
                ControlMissionDeliveryExpirationPolicy(),
                signer_v1,
            )
        )

    return TestClient(app)


def test_missing_protocol_header_delivers_v1(
    tmp_path: Path,
) -> None:
    store = ControlMissionStore()
    mission = build_mission()

    store.push(
        mission
    )

    client = build_client(
        tmp_path,
        store,
    )

    response = client.get(
        "/control/missions/next",
        headers=authentication_headers(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "available"

    assert (
        "security_sequence"
        not in payload["mission"]
    )

    restored = ControlMissionSerializer.deserialize(
        payload["mission"]
    )

    verifier = ControlMissionSigner(
        SIGNING_SECRET
    )

    assert verifier.verify(
        restored,
        payload["mission_signature"],
    )

    assert store.size() == 0


def test_explicit_v1_protocol_delivers_v1(
    tmp_path: Path,
) -> None:
    store = ControlMissionStore()
    mission = build_mission()

    store.push(
        mission
    )

    client = build_client(
        tmp_path,
        store,
    )

    response = client.get(
        "/control/missions/next",
        headers=authentication_headers(
            protocol="V1"
        ),
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        "security_sequence"
        not in payload["mission"]
    )

    restored = ControlMissionSerializer.deserialize(
        payload["mission"]
    )

    verifier = ControlMissionSigner(
        SIGNING_SECRET
    )

    assert verifier.verify(
        restored,
        payload["mission_signature"],
    )

    assert store.size() == 0


def test_explicit_v2_protocol_delivers_v2(
    tmp_path: Path,
) -> None:
    store = ControlMissionStore()
    mission = build_mission()

    store.push(
        mission
    )

    client = build_client(
        tmp_path,
        store,
        enable_v2=True,
    )

    response = client.get(
        "/control/missions/next",
        headers=authentication_headers(
            protocol="V2"
        ),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "available"

    assert (
        payload["mission"]["security_sequence"]
        == SECURITY_SEQUENCE
    )

    restored = ControlMissionSerializerV2.deserialize(
        payload["mission"]
    )

    verifier = ControlMissionSignerV2(
        SIGNING_SECRET
    )

    assert verifier.verify(
        restored,
        payload["mission_signature"],
    )

    assert store.size() == 0


def test_unsupported_protocol_is_rejected_before_queue_pop(
    tmp_path: Path,
) -> None:
    store = ControlMissionStore()

    store.push(
        build_mission()
    )

    client = build_client(
        tmp_path,
        store,
    )

    response = client.get(
        "/control/missions/next",
        headers=authentication_headers(
            protocol="V999"
        ),
    )

    assert response.status_code == 400

    assert response.json() == {
        "detail": (
            "Unsupported TODOBA mission protocol."
        )
    }

    assert store.size() == 1