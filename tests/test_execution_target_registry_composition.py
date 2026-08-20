import pytest

from backend.trading.execution.execution_target_registry import (
    ExecutionTarget,
    ExecutionTargetRegistry,
    build_execution_target_registry,
)


def test_build_execution_target_registry_from_config() -> None:
    targets = (
        {
            "agent_id": "trusted-agent-001",
            "account_fingerprint": "account-a",
        },
        {
            "agent_id": "trusted-agent-003",
            "account_fingerprint": "account-c",
        },
    )

    registry = build_execution_target_registry(
        targets
    )

    assert isinstance(
        registry,
        ExecutionTargetRegistry,
    )

    assert registry.size() == 2

    assert registry.get(
        agent_id="trusted-agent-001"
    ) == ExecutionTarget(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    assert registry.get(
        agent_id="trusted-agent-003"
    ) == ExecutionTarget(
        agent_id="trusted-agent-003",
        account_fingerprint="account-c",
    )


def test_build_execution_target_registry_preserves_target_order() -> None:
    targets = (
        {
            "agent_id": "trusted-agent-003",
            "account_fingerprint": "account-c",
        },
        {
            "agent_id": "trusted-agent-001",
            "account_fingerprint": "account-a",
        },
    )

    registry = build_execution_target_registry(
        targets
    )

    assert [
        target.agent_id
        for target in registry.all()
    ] == [
        "trusted-agent-003",
        "trusted-agent-001",
    ]


def test_build_execution_target_registry_rejects_invalid_target_record() -> None:
    targets = (
        {
            "agent_id": "trusted-agent-001",
        },
    )

    with pytest.raises(
        ValueError,
        match="account_fingerprint",
    ):
        build_execution_target_registry(
            targets
        )