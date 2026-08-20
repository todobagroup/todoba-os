import pytest

from backend.trading.execution.execution_target_registry import (
    ExecutionTarget,
    ExecutionTargetRegistry,
)


def test_execution_target_registry_registers_and_gets_target() -> None:
    registry = ExecutionTargetRegistry()

    target = ExecutionTarget(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    registered = registry.register(
        target
    )

    assert registered == target

    assert registry.get(
        agent_id="trusted-agent-001"
    ) == target

    assert registry.size() == 1


def test_execution_target_registry_preserves_registration_order() -> None:
    registry = ExecutionTargetRegistry()

    target_a = ExecutionTarget(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    target_b = ExecutionTarget(
        agent_id="trusted-agent-002",
        account_fingerprint="account-b",
    )

    registry.register(
        target_a
    )

    registry.register(
        target_b
    )

    assert registry.all() == (
        target_a,
        target_b,
    )


def test_execution_target_registry_is_idempotent_for_same_target() -> None:
    registry = ExecutionTargetRegistry()

    first = ExecutionTarget(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    second = ExecutionTarget(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    registered_first = registry.register(
        first
    )

    registered_second = registry.register(
        second
    )

    assert registered_first == first
    assert registered_second == first

    assert registry.size() == 1


def test_execution_target_registry_rejects_conflicting_account() -> None:
    registry = ExecutionTargetRegistry()

    registry.register(
        ExecutionTarget(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )
    )

    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        registry.register(
            ExecutionTarget(
                agent_id="trusted-agent-001",
                account_fingerprint="account-b",
            )
        )


def test_execution_target_registry_returns_none_for_unknown_agent() -> None:
    registry = ExecutionTargetRegistry()

    assert registry.get(
        agent_id="unknown-agent"
    ) is None