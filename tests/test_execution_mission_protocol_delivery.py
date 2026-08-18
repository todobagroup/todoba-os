from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_api import (
    create_execution_mission_router,
)
from backend.trading.execution.execution_mission_serializer import (
    ExecutionMissionSerializer,
)
from backend.trading.execution.execution_mission_serializer_v2 import (
    ExecutionMissionSerializerV2,
)
from backend.trading.execution.execution_mission_signer import (
    ExecutionMissionSigner,
)
from backend.trading.execution.execution_mission_signer_v2 import (
    ExecutionMissionSignerV2,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "proof-execution-protocol-agent-secret"
SIGNING_SECRET = "proof-execution-protocol-signing-secret"

MISSION_ID = "execution-protocol-001"
SECURITY_SEQUENCE = 42


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA execution protocol proof",
        created_at="2026-08-18T00:00:00Z",
        expires_at="2026-08-18T23:59:59Z",
        sequence=168001,
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
    store: ExecutionMissionStore,
    *,
    enable_v2: bool = False,
) -> TestClient:
    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    signer_v1 = ExecutionMissionSigner(
        SIGNING_SECRET
    )

    app = FastAPI()

    if enable_v2:
        signer_v2 = ExecutionMissionSignerV2(
            SIGNING_SECRET
        )

        app.include_router(
            create_execution_mission_router(
                store,
                authenticator,
                signer=signer_v1,
                signer_v2=signer_v2,
            )
        )
    else:
        app.include_router(
            create_execution_mission_router(
                store,
                authenticator,
                signer=signer_v1,
            )
        )

    return TestClient(app)


def test_missing_protocol_header_delivers_v1() -> None:
    store = ExecutionMissionStore()
    mission = build_mission()

    store.push(
        mission
    )

    client = build_client(
        store
    )

    response = client.get(
        "/missions/next",
        headers=authentication_headers(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "available"

    assert (
        "security_sequence"
        not in payload["mission"]
    )

    restored = ExecutionMissionSerializer.deserialize(
        payload["mission"]
    )

    verifier = ExecutionMissionSigner(
        SIGNING_SECRET
    )

    assert verifier.verify(
        restored,
        payload["mission_signature"],
    )

    assert store.size() == 0


def test_explicit_v1_protocol_delivers_v1() -> None:
    store = ExecutionMissionStore()
    mission = build_mission()

    store.push(
        mission
    )

    client = build_client(
        store
    )

    response = client.get(
        "/missions/next",
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

    restored = ExecutionMissionSerializer.deserialize(
        payload["mission"]
    )

    verifier = ExecutionMissionSigner(
        SIGNING_SECRET
    )

    assert verifier.verify(
        restored,
        payload["mission_signature"],
    )

    assert store.size() == 0


def test_explicit_v2_protocol_delivers_v2() -> None:
    store = ExecutionMissionStore()
    mission = build_mission()

    store.push(
        mission
    )

    client = build_client(
        store,
        enable_v2=True,
    )

    response = client.get(
        "/missions/next",
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

    restored = ExecutionMissionSerializerV2.deserialize(
        payload["mission"]
    )

    verifier = ExecutionMissionSignerV2(
        SIGNING_SECRET
    )

    assert verifier.verify(
        restored,
        payload["mission_signature"],
    )

    assert store.size() == 0


def test_unsupported_protocol_is_rejected_before_queue_pop() -> None:
    store = ExecutionMissionStore()

    store.push(
        build_mission()
    )

    client = build_client(
        store
    )

    response = client.get(
        "/missions/next",
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