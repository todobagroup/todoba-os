import pytest

from backend.trading.execution.trusted_agent_signing_key_registry import (
    TrustedAgentSigningKeyRegistry,
)


def test_registry_stores_independent_agent_signing_keys() -> None:
    registry = TrustedAgentSigningKeyRegistry()

    registry.register(
        agent_id="trusted-agent-001",
        signing_secret="execution-key-a",
    )

    registry.register(
        agent_id="trusted-agent-002",
        signing_secret="execution-key-b",
    )

    assert (
        registry.get_secret(
            agent_id="trusted-agent-001"
        )
        == "execution-key-a"
    )

    assert (
        registry.get_secret(
            agent_id="trusted-agent-002"
        )
        == "execution-key-b"
    )

    assert registry.size() == 2


def test_identical_signing_key_registration_is_idempotent() -> None:
    registry = TrustedAgentSigningKeyRegistry()

    first = registry.register(
        agent_id="trusted-agent-001",
        signing_secret="execution-key-a",
    )

    second = registry.register(
        agent_id="trusted-agent-001",
        signing_secret="execution-key-a",
    )

    assert first == "execution-key-a"
    assert second == "execution-key-a"
    assert registry.size() == 1


def test_conflicting_signing_key_is_rejected() -> None:
    registry = TrustedAgentSigningKeyRegistry()

    registry.register(
        agent_id="trusted-agent-001",
        signing_secret="execution-key-a",
    )

    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        registry.register(
            agent_id="trusted-agent-001",
            signing_secret="different-key",
        )


def test_unknown_agent_returns_none() -> None:
    registry = TrustedAgentSigningKeyRegistry()

    assert (
        registry.get_secret(
            agent_id="unknown-agent"
        )
        is None
    )


def test_separate_registry_instances_isolate_signing_domains() -> None:
    execution_registry = TrustedAgentSigningKeyRegistry()
    control_registry = TrustedAgentSigningKeyRegistry()

    execution_registry.register(
        agent_id="trusted-agent-001",
        signing_secret="execution-key-a",
    )

    control_registry.register(
        agent_id="trusted-agent-001",
        signing_secret="control-key-a",
    )

    assert (
        execution_registry.get_secret(
            agent_id="trusted-agent-001"
        )
        == "execution-key-a"
    )

    assert (
        control_registry.get_secret(
            agent_id="trusted-agent-001"
        )
        == "control-key-a"
    )

def test_signing_secret_is_preserved_exactly() -> None:
    registry = TrustedAgentSigningKeyRegistry()

    secret = "  signing-??-secret  "

    registered = registry.register(
        agent_id="trusted-agent-opaque",
        signing_secret=secret,
    )

    restored = registry.get_secret(
        agent_id="trusted-agent-opaque"
    )

    assert registered == secret
    assert restored == secret

    assert registered.startswith("  ")
    assert registered.endswith("  ")
