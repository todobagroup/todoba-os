"""
TODOBA Customer Deployment Execution Target Projection Tests

Proof:

durable CustomerDeploymentRegistry
+
authoritative TrustedAgentAccountBindingStore
->
routing-only ExecutionTargetRegistry

The projection is additive, idempotent, fail-closed,
and does not depend on customer secret material.
"""

from pathlib import Path

import pytest

from backend.commercial.customer_deployment_execution_target_projection import (
    CustomerDeploymentExecutionTargetProjection,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.trading.execution.execution_target_registry import (
    ExecutionTarget,
    ExecutionTargetRegistry,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


def _build_initialized_sources(
    tmp_path: Path,
) -> tuple[
    CustomerDeploymentRegistry,
    TrustedAgentAccountBindingStore,
]:
    deployment_registry = (
        CustomerDeploymentRegistry(
            tmp_path
            / "customer_deployments.json"
        )
    )

    deployment_registry.initialize_empty()

    account_binding_store = (
        TrustedAgentAccountBindingStore(
            tmp_path
            / "account_bindings.json"
        )
    )

    account_binding_store.initialize_empty()

    return (
        deployment_registry,
        account_binding_store,
    )


def _register_deployment(
    deployment_registry: CustomerDeploymentRegistry,
    *,
    customer_id: str,
    deployment_id: str,
    agent_id: str,
) -> None:
    deployment_registry.register(
        CustomerDeployment(
            customer_id=customer_id,
            deployment_id=deployment_id,
            agent_id=agent_id,
        )
    )


def _bind_account(
    account_binding_store: TrustedAgentAccountBindingStore,
    *,
    agent_id: str,
    account_fingerprint: str,
) -> None:
    account_binding_store.bind(
        agent_id=agent_id,
        account_fingerprint=account_fingerprint,
    )


def test_projects_complete_single_deployment(
    tmp_path: Path,
) -> None:
    (
        deployments,
        bindings,
    ) = _build_initialized_sources(
        tmp_path
    )

    _register_deployment(
        deployments,
        customer_id="customer-a",
        deployment_id="deployment-a",
        agent_id="trusted-agent-a",
    )

    _bind_account(
        bindings,
        agent_id="trusted-agent-a",
        account_fingerprint="server-a:1001",
    )

    targets = ExecutionTargetRegistry()

    projection = (
        CustomerDeploymentExecutionTargetProjection(
            deployment_registry=deployments,
            account_binding_store=bindings,
            execution_target_registry=targets,
        )
    )

    assert projection.project() == 1
    assert targets.size() == 1

    target = targets.get(
        agent_id="trusted-agent-a"
    )

    assert target is not None
    assert target.agent_id == "trusted-agent-a"
    assert (
        target.account_fingerprint
        == "server-a:1001"
    )


def test_projects_multiple_deployments(
    tmp_path: Path,
) -> None:
    (
        deployments,
        bindings,
    ) = _build_initialized_sources(
        tmp_path
    )

    _register_deployment(
        deployments,
        customer_id="customer-a",
        deployment_id="deployment-a",
        agent_id="trusted-agent-a",
    )

    _register_deployment(
        deployments,
        customer_id="customer-b",
        deployment_id="deployment-b",
        agent_id="trusted-agent-b",
    )

    _bind_account(
        bindings,
        agent_id="trusted-agent-a",
        account_fingerprint="server-a:1001",
    )

    _bind_account(
        bindings,
        agent_id="trusted-agent-b",
        account_fingerprint="server-b:1002",
    )

    targets = ExecutionTargetRegistry()

    projection = (
        CustomerDeploymentExecutionTargetProjection(
            deployment_registry=deployments,
            account_binding_store=bindings,
            execution_target_registry=targets,
        )
    )

    assert projection.project() == 2
    assert targets.size() == 2

    assert (
        targets.get(
            agent_id="trusted-agent-a"
        ).account_fingerprint
        == "server-a:1001"
    )

    assert (
        targets.get(
            agent_id="trusted-agent-b"
        ).account_fingerprint
        == "server-b:1002"
    )


def test_repeated_projection_is_idempotent(
    tmp_path: Path,
) -> None:
    (
        deployments,
        bindings,
    ) = _build_initialized_sources(
        tmp_path
    )

    _register_deployment(
        deployments,
        customer_id="customer-a",
        deployment_id="deployment-a",
        agent_id="trusted-agent-a",
    )

    _bind_account(
        bindings,
        agent_id="trusted-agent-a",
        account_fingerprint="server-a:1001",
    )

    targets = ExecutionTargetRegistry()

    projection = (
        CustomerDeploymentExecutionTargetProjection(
            deployment_registry=deployments,
            account_binding_store=bindings,
            execution_target_registry=targets,
        )
    )

    assert projection.project() == 1
    assert projection.project() == 1

    assert targets.size() == 1


def test_projection_retains_same_runtime_registry_object(
    tmp_path: Path,
) -> None:
    (
        deployments,
        bindings,
    ) = _build_initialized_sources(
        tmp_path
    )

    _register_deployment(
        deployments,
        customer_id="customer-a",
        deployment_id="deployment-a",
        agent_id="trusted-agent-a",
    )

    _bind_account(
        bindings,
        agent_id="trusted-agent-a",
        account_fingerprint="server-a:1001",
    )

    targets = ExecutionTargetRegistry()

    projection = (
        CustomerDeploymentExecutionTargetProjection(
            deployment_registry=deployments,
            account_binding_store=bindings,
            execution_target_registry=targets,
        )
    )

    original_registry_identity = id(
        targets
    )

    assert projection.project() == 1

    assert id(targets) == original_registry_identity

    assert (
        projection._execution_target_registry
        is targets
    )


def test_missing_binding_fails_before_any_mutation(
    tmp_path: Path,
) -> None:
    (
        deployments,
        bindings,
    ) = _build_initialized_sources(
        tmp_path
    )

    _register_deployment(
        deployments,
        customer_id="customer-a",
        deployment_id="deployment-a",
        agent_id="trusted-agent-a",
    )

    _register_deployment(
        deployments,
        customer_id="customer-b",
        deployment_id="deployment-b",
        agent_id="trusted-agent-b",
    )

    _bind_account(
        bindings,
        agent_id="trusted-agent-a",
        account_fingerprint="server-a:1001",
    )

    targets = ExecutionTargetRegistry()

    projection = (
        CustomerDeploymentExecutionTargetProjection(
            deployment_registry=deployments,
            account_binding_store=bindings,
            execution_target_registry=targets,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="account binding is missing",
    ):
        projection.project()

    assert targets.size() == 0


def test_runtime_conflict_fails_before_partial_mutation(
    tmp_path: Path,
) -> None:
    (
        deployments,
        bindings,
    ) = _build_initialized_sources(
        tmp_path
    )

    _register_deployment(
        deployments,
        customer_id="customer-a",
        deployment_id="deployment-a",
        agent_id="trusted-agent-a",
    )

    _register_deployment(
        deployments,
        customer_id="customer-b",
        deployment_id="deployment-b",
        agent_id="trusted-agent-b",
    )

    _bind_account(
        bindings,
        agent_id="trusted-agent-a",
        account_fingerprint="server-a:1001",
    )

    _bind_account(
        bindings,
        agent_id="trusted-agent-b",
        account_fingerprint="server-b:1002",
    )

    targets = ExecutionTargetRegistry()

    targets.register(
        ExecutionTarget(
            agent_id="trusted-agent-b",
            account_fingerprint="wrong-server:9999",
        )
    )

    projection = (
        CustomerDeploymentExecutionTargetProjection(
            deployment_registry=deployments,
            account_binding_store=bindings,
            execution_target_registry=targets,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="runtime conflict",
    ):
        projection.project()

    assert targets.size() == 1

    assert (
        targets.get(
            agent_id="trusted-agent-a"
        )
        is None
    )

    existing = targets.get(
        agent_id="trusted-agent-b"
    )

    assert existing is not None
    assert (
        existing.account_fingerprint
        == "wrong-server:9999"
    )


def test_uninitialized_sources_fail_closed(
    tmp_path: Path,
) -> None:
    uninitialized_deployments = (
        CustomerDeploymentRegistry(
            tmp_path
            / "uninitialized_deployments.json"
        )
    )

    ready_bindings = (
        TrustedAgentAccountBindingStore(
            tmp_path
            / "ready_bindings.json"
        )
    )

    ready_bindings.initialize_empty()

    targets = ExecutionTargetRegistry()

    projection = (
        CustomerDeploymentExecutionTargetProjection(
            deployment_registry=(
                uninitialized_deployments
            ),
            account_binding_store=ready_bindings,
            execution_target_registry=targets,
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Customer deployment registry "
            "is not initialized"
        ),
    ):
        projection.project()

    assert targets.size() == 0

    ready_deployments = (
        CustomerDeploymentRegistry(
            tmp_path
            / "ready_deployments.json"
        )
    )

    ready_deployments.initialize_empty()

    uninitialized_bindings = (
        TrustedAgentAccountBindingStore(
            tmp_path
            / "uninitialized_bindings.json"
        )
    )

    second_targets = ExecutionTargetRegistry()

    second_projection = (
        CustomerDeploymentExecutionTargetProjection(
            deployment_registry=ready_deployments,
            account_binding_store=(
                uninitialized_bindings
            ),
            execution_target_registry=(
                second_targets
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Trusted Agent account binding store "
            "is not initialized"
        ),
    ):
        second_projection.project()

    assert second_targets.size() == 0


@pytest.mark.parametrize(
    (
        "deployment_registry",
        "account_binding_store",
        "execution_target_registry",
        "expected_message",
    ),
    (
        (
            object(),
            object(),
            object(),
            "deployment_registry must be",
        ),
        (
            "not-a-registry",
            object(),
            object(),
            "deployment_registry must be",
        ),
    ),
)
def test_rejects_wrong_owner_types_at_first_invalid_boundary(
    deployment_registry,
    account_binding_store,
    execution_target_registry,
    expected_message: str,
) -> None:
    with pytest.raises(
        TypeError,
        match=expected_message,
    ):
        CustomerDeploymentExecutionTargetProjection(
            deployment_registry=(
                deployment_registry
            ),
            account_binding_store=(
                account_binding_store
            ),
            execution_target_registry=(
                execution_target_registry
            ),
        )


def test_rejects_wrong_binding_and_target_registry_types(
    tmp_path: Path,
) -> None:
    deployments = CustomerDeploymentRegistry(
        tmp_path
        / "deployments.json"
    )

    deployments.initialize_empty()

    bindings = TrustedAgentAccountBindingStore(
        tmp_path
        / "bindings.json"
    )

    bindings.initialize_empty()

    with pytest.raises(
        TypeError,
        match="account_binding_store must be",
    ):
        CustomerDeploymentExecutionTargetProjection(
            deployment_registry=deployments,
            account_binding_store=object(),
            execution_target_registry=(
                ExecutionTargetRegistry()
            ),
        )

    with pytest.raises(
        TypeError,
        match="execution_target_registry must be",
    ):
        CustomerDeploymentExecutionTargetProjection(
            deployment_registry=deployments,
            account_binding_store=bindings,
            execution_target_registry=object(),
        )


def test_routing_projection_has_no_secret_domain_dependency() -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / (
            "customer_deployment_"
            "execution_target_projection.py"
        )
    )

    source = source_path.read_text(
        encoding="utf-8"
    )

    forbidden_tokens = (
        "CustomerDeploymentSecretStore",
        "TrustedAgentCredentialRegistry",
        "TrustedAgentSigningKeyRegistry",
        "agent_secret",
        "signing_secret",
    )

    for token in forbidden_tokens:
        assert token not in source
