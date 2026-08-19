import pytest

from backend.trading.execution.trusted_agent_credential_registry import (
    TrustedAgentCredentialRegistry,
)


def test_registry_stores_independent_agent_credentials() -> None:
    registry = TrustedAgentCredentialRegistry()

    registry.register(
        agent_id="trusted-agent-001",
        agent_secret="secret-a",
    )

    registry.register(
        agent_id="trusted-agent-002",
        agent_secret="secret-b",
    )

    assert (
        registry.get_secret(
            agent_id="trusted-agent-001"
        )
        == "secret-a"
    )

    assert (
        registry.get_secret(
            agent_id="trusted-agent-002"
        )
        == "secret-b"
    )

    assert registry.size() == 2


def test_identical_registration_is_idempotent() -> None:
    registry = TrustedAgentCredentialRegistry()

    first = registry.register(
        agent_id="trusted-agent-001",
        agent_secret="secret-a",
    )

    second = registry.register(
        agent_id="trusted-agent-001",
        agent_secret="secret-a",
    )

    assert first == "secret-a"
    assert second == "secret-a"
    assert registry.size() == 1


def test_conflicting_agent_secret_is_rejected() -> None:
    registry = TrustedAgentCredentialRegistry()

    registry.register(
        agent_id="trusted-agent-001",
        agent_secret="secret-a",
    )

    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        registry.register(
            agent_id="trusted-agent-001",
            agent_secret="different-secret",
        )


def test_unknown_agent_returns_none() -> None:
    registry = TrustedAgentCredentialRegistry()

    assert (
        registry.get_secret(
            agent_id="unknown-agent"
        )
        is None
    )