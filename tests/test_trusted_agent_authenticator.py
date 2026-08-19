import pytest

from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)
from backend.trading.execution.trusted_agent_credential_registry import (
    TrustedAgentCredentialRegistry,
)


def test_authenticate_accepts_matching_agent_and_secret() -> None:
    authenticator = TrustedAgentAuthenticator(
        agent_id="trusted-agent-001",
        agent_secret="secure-secret",
    )

    authenticated = authenticator.authenticate(
        agent_id="trusted-agent-001",
        authorization="Bearer secure-secret",
    )

    assert authenticated is True


@pytest.mark.parametrize(
    (
        "agent_id",
        "authorization",
    ),
    [
        (
            None,
            "Bearer secure-secret",
        ),
        (
            "trusted-agent-001",
            None,
        ),
        (
            "wrong-agent",
            "Bearer secure-secret",
        ),
        (
            "trusted-agent-001",
            "Bearer wrong-secret",
        ),
        (
            "trusted-agent-001",
            "secure-secret",
        ),
        (
            "trusted-agent-001",
            "Bearer ",
        ),
    ],
)
def test_authenticate_rejects_invalid_credentials(
    agent_id: str | None,
    authorization: str | None,
) -> None:
    authenticator = TrustedAgentAuthenticator(
        agent_id="trusted-agent-001",
        agent_secret="secure-secret",
    )

    authenticated = authenticator.authenticate(
        agent_id=agent_id,
        authorization=authorization,
    )

    assert authenticated is False


@pytest.mark.parametrize(
    (
        "agent_id",
        "agent_secret",
        "expected_message",
    ),
    [
        (
            "",
            "secure-secret",
            "agent_id is required.",
        ),
        (
            "trusted-agent-001",
            "",
            "agent_secret is required.",
        ),
    ],
)
def test_constructor_rejects_empty_credentials(
    agent_id: str,
    agent_secret: str,
    expected_message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        TrustedAgentAuthenticator(
            agent_id=agent_id,
            agent_secret=agent_secret,
        )


def test_authenticate_supports_multiple_registered_agents() -> None:
    registry = TrustedAgentCredentialRegistry()

    registry.register(
        agent_id="trusted-agent-001",
        agent_secret="secret-a",
    )

    registry.register(
        agent_id="trusted-agent-002",
        agent_secret="secret-b",
    )

    authenticator = TrustedAgentAuthenticator(
        credential_registry=registry,
    )

    assert authenticator.authenticate(
        agent_id="trusted-agent-001",
        authorization="Bearer secret-a",
    )

    assert authenticator.authenticate(
        agent_id="trusted-agent-002",
        authorization="Bearer secret-b",
    )


def test_multi_agent_authentication_rejects_cross_agent_secret() -> None:
    registry = TrustedAgentCredentialRegistry()

    registry.register(
        agent_id="trusted-agent-001",
        agent_secret="secret-a",
    )

    registry.register(
        agent_id="trusted-agent-002",
        agent_secret="secret-b",
    )

    authenticator = TrustedAgentAuthenticator(
        credential_registry=registry,
    )

    assert not authenticator.authenticate(
        agent_id="trusted-agent-001",
        authorization="Bearer secret-b",
    )

    assert not authenticator.authenticate(
        agent_id="trusted-agent-002",
        authorization="Bearer secret-a",
    )


def test_multi_agent_authentication_rejects_unknown_agent() -> None:
    registry = TrustedAgentCredentialRegistry()

    registry.register(
        agent_id="trusted-agent-001",
        agent_secret="secret-a",
    )

    authenticator = TrustedAgentAuthenticator(
        credential_registry=registry,
    )

    assert not authenticator.authenticate(
        agent_id="unknown-agent",
        authorization="Bearer secret-a",
    )