from fastapi import Depends
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.trusted_agent_protocol_dependency import (
    create_trusted_agent_protocol_dependency,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "proof-protocol-agent-secret"


def build_client() -> TestClient:
    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    require_trusted_agent_protocol = (
        create_trusted_agent_protocol_dependency(
            authenticator
        )
    )

    app = FastAPI()

    @app.get("/proof")
    def proof(
        agent_context=Depends(
            require_trusted_agent_protocol
        ),
    ):
        return {
            "agent_id": agent_context.agent_id,
            "mission_protocol": (
                agent_context.mission_protocol
            ),
        }

    return TestClient(app)


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


def test_missing_protocol_defaults_to_v1() -> None:
    client = build_client()

    response = client.get(
        "/proof",
        headers=authentication_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "agent_id": AGENT_ID,
        "mission_protocol": "V1",
    }


def test_explicit_v1_protocol_is_accepted() -> None:
    client = build_client()

    response = client.get(
        "/proof",
        headers=authentication_headers(
            protocol="V1"
        ),
    )

    assert response.status_code == 200
    assert response.json() == {
        "agent_id": AGENT_ID,
        "mission_protocol": "V1",
    }


def test_explicit_v2_protocol_is_accepted() -> None:
    client = build_client()

    response = client.get(
        "/proof",
        headers=authentication_headers(
            protocol="V2"
        ),
    )

    assert response.status_code == 200
    assert response.json() == {
        "agent_id": AGENT_ID,
        "mission_protocol": "V2",
    }


def test_unsupported_protocol_fails_closed() -> None:
    client = build_client()

    response = client.get(
        "/proof",
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


def test_authentication_fails_before_protocol_negotiation() -> None:
    client = build_client()

    response = client.get(
        "/proof",
        headers={
            "X-TODOBA-Agent-ID": AGENT_ID,
            "Authorization": "Bearer wrong-secret",
            "X-TODOBA-Mission-Protocol": "V2",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": (
            "Trusted Agent authentication failed."
        )
    }