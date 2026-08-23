import json

import pytest

from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)


def build_deployment(
    *,
    customer_id: str = "customer-001",
    deployment_id: str = "deployment-001",
    agent_id: str = "trusted-agent-004",
) -> CustomerDeployment:
    return CustomerDeployment(
        customer_id=customer_id,
        deployment_id=deployment_id,
        agent_id=agent_id,
    )


def test_registry_requires_explicit_initialization(
    tmp_path,
) -> None:
    registry = CustomerDeploymentRegistry(
        tmp_path / "customer_deployments.json"
    )

    assert not registry.is_ready()

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        registry.size()


def test_initialize_empty_creates_durable_registry(
    tmp_path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_deployments.json"
    )

    registry = CustomerDeploymentRegistry(
        storage_path
    )

    registry.initialize_empty()

    assert registry.is_ready()
    assert registry.size() == 0
    assert storage_path.is_file()

    payload = json.loads(
        storage_path.read_text(
            encoding="utf-8"
        )
    )

    assert payload == {
        "version": 1,
        "deployments": [],
    }


def test_register_persists_and_restores_deployment(
    tmp_path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_deployments.json"
    )

    registry = CustomerDeploymentRegistry(
        storage_path
    )
    registry.initialize_empty()

    deployment = build_deployment()

    result = registry.register(
        deployment
    )

    assert result == deployment
    assert registry.size() == 1

    restored = CustomerDeploymentRegistry(
        storage_path
    )

    assert restored.is_ready()
    assert restored.size() == 1

    assert restored.get(
        deployment_id="deployment-001"
    ) == deployment

    assert restored.get_by_agent_id(
        agent_id="trusted-agent-004"
    ) == deployment


def test_identical_registration_is_idempotent(
    tmp_path,
) -> None:
    registry = CustomerDeploymentRegistry(
        tmp_path
        / "customer_deployments.json"
    )
    registry.initialize_empty()

    deployment = build_deployment()

    first = registry.register(
        deployment
    )
    second = registry.register(
        deployment
    )

    assert first == deployment
    assert second == deployment
    assert registry.size() == 1


def test_conflicting_deployment_identity_is_rejected(
    tmp_path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_deployments.json"
    )

    registry = CustomerDeploymentRegistry(
        storage_path
    )
    registry.initialize_empty()

    original = build_deployment()

    registry.register(
        original
    )

    durable_before = (
        storage_path.read_text(
            encoding="utf-8"
        )
    )

    conflicting = build_deployment(
        customer_id="customer-002",
        deployment_id="deployment-001",
        agent_id="trusted-agent-005",
    )

    with pytest.raises(
        ValueError,
        match="different identity",
    ):
        registry.register(
            conflicting
        )

    assert registry.size() == 1

    assert (
        storage_path.read_text(
            encoding="utf-8"
        )
        == durable_before
    )

    assert registry.get(
        deployment_id="deployment-001"
    ) == original


def test_agent_identity_cannot_belong_to_two_deployments(
    tmp_path,
) -> None:
    registry = CustomerDeploymentRegistry(
        tmp_path
        / "customer_deployments.json"
    )
    registry.initialize_empty()

    first = build_deployment()

    second = build_deployment(
        customer_id="customer-002",
        deployment_id="deployment-002",
        agent_id="trusted-agent-004",
    )

    registry.register(
        first
    )

    with pytest.raises(
        ValueError,
        match="already assigned",
    ):
        registry.register(
            second
        )

    assert registry.size() == 1
    assert registry.get_by_agent_id(
        agent_id="trusted-agent-004"
    ) == first


def test_one_customer_can_own_multiple_deployments(
    tmp_path,
) -> None:
    registry = CustomerDeploymentRegistry(
        tmp_path
        / "customer_deployments.json"
    )
    registry.initialize_empty()

    first = build_deployment()

    second = build_deployment(
        customer_id="customer-001",
        deployment_id="deployment-002",
        agent_id="trusted-agent-005",
    )

    registry.register(
        first
    )
    registry.register(
        second
    )

    assert registry.size() == 2
    assert registry.all() == (
        first,
        second,
    )


def test_restore_rejects_duplicate_agent_identity(
    tmp_path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_deployments.json"
    )

    storage_path.write_text(
        json.dumps(
            {
                "version": 1,
                "deployments": [
                    {
                        "customer_id": "customer-001",
                        "deployment_id": "deployment-001",
                        "agent_id": "trusted-agent-004",
                    },
                    {
                        "customer_id": "customer-002",
                        "deployment_id": "deployment-002",
                        "agent_id": "trusted-agent-004",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate Trusted Agent identity",
    ):
        CustomerDeploymentRegistry(
            storage_path
        )


def test_register_write_failure_does_not_advance_memory(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_path = (
        tmp_path
        / "customer_deployments.json"
    )

    registry = CustomerDeploymentRegistry(
        storage_path
    )
    registry.initialize_empty()

    deployment = build_deployment()

    durable_before = (
        storage_path.read_text(
            encoding="utf-8"
        )
    )

    def fail_write(
        deployments,
    ) -> None:
        raise OSError(
            "simulated durable write failure"
        )

    monkeypatch.setattr(
        registry,
        "_write_deployments",
        fail_write,
    )

    with pytest.raises(
        OSError,
        match="simulated durable write failure",
    ):
        registry.register(
            deployment
        )

    assert registry.size() == 0

    assert registry.get(
        deployment_id="deployment-001"
    ) is None

    assert registry.get_by_agent_id(
        agent_id="trusted-agent-004"
    ) is None

    assert (
        storage_path.read_text(
            encoding="utf-8"
        )
        == durable_before
    )
