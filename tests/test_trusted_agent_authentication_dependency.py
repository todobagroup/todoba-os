from fastapi import Depends
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.trusted_agent_authentication_dependency import (
    create_trusted_agent_authentication_dependency,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


def create_test_client() -> TestClient:
    authenticator = TrustedAgentAuthenticator(
        agent_id="trusted-agent-001",
        agent_secret="secure-secret",
    )

    require_trusted_agent = (
        create_trusted_agent_authentication_dependency(
            authenticator
        )
    )

    app = FastAPI()

    @app.get(
        "/protected",
        dependencies=[
            Depends(
                require_trusted_agent
            )
        ],
    )
    def protected_endpoint() -> dict[str, str]:
        return {
            "status": "authenticated",
        }

    return TestClient(
        app
    )


def test_dependency_accepts_valid_credentials() -> None:
    client = create_test_client()

    response = client.get(
        "/protected",
        headers={
            "X-TODOBA-Agent-ID": "trusted-agent-001",
            "Authorization": "Bearer secure-secret",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "authenticated",
    }


def test_dependency_rejects_missing_credentials() -> None:
    client = create_test_client()

    response = client.get(
        "/protected"
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Trusted Agent authentication failed.",
    }
    assert response.headers["www-authenticate"] == "Bearer"


def test_dependency_rejects_invalid_secret() -> None:
    client = create_test_client()

    response = client.get(
        "/protected",
        headers={
            "X-TODOBA-Agent-ID": "trusted-agent-001",
            "Authorization": "Bearer wrong-secret",
        },
    )

    assert response.status_code == 401


def test_dependency_requires_authenticator() -> None:
    try:
        create_trusted_agent_authentication_dependency(
            object()
        )
    except TypeError as error:
        assert str(error) == (
            "create_trusted_agent_authentication_dependency "
            "requires TrustedAgentAuthenticator."
        )
    else:
        raise AssertionError(
            "TypeError was not raised."
        )