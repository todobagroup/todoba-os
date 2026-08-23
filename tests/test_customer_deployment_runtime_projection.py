import pytest
from cryptography.hazmat.primitives.ciphers.aead import (
    AESGCM,
)

from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_deployment_runtime_projection import (
    CustomerDeploymentRuntimeProjection,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecrets,
    CustomerDeploymentSecretStore,
)
from backend.trading.execution.execution_target_registry import (
    ExecutionTarget,
    ExecutionTargetRegistry,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)
from backend.trading.execution.trusted_agent_credential_registry import (
    TrustedAgentCredentialRegistry,
)
from backend.trading.execution.trusted_agent_signing_key_registry import (
    TrustedAgentSigningKeyRegistry,
)


def build_sources(
    tmp_path,
) -> tuple[
    CustomerDeploymentRegistry,
    CustomerDeploymentSecretStore,
    TrustedAgentAccountBindingStore,
]:
    deployment_registry = (
        CustomerDeploymentRegistry(
            tmp_path / "customer_deployments.json"
        )
    )
    deployment_registry.initialize_empty()

    secret_store = CustomerDeploymentSecretStore(
        tmp_path / "customer_deployment_secrets.json",
        master_key=AESGCM.generate_key(
            bit_length=256
        ),
    )
    secret_store.initialize_empty()

    account_binding_store = (
        TrustedAgentAccountBindingStore(
            tmp_path / "account_bindings.json"
        )
    )
    account_binding_store.initialize_empty()

    return (
        deployment_registry,
        secret_store,
        account_binding_store,
    )


def build_runtime(
) -> tuple[
    TrustedAgentCredentialRegistry,
    TrustedAgentSigningKeyRegistry,
    TrustedAgentSigningKeyRegistry,
    ExecutionTargetRegistry,
]:
    return (
        TrustedAgentCredentialRegistry(),
        TrustedAgentSigningKeyRegistry(),
        TrustedAgentSigningKeyRegistry(),
        ExecutionTargetRegistry(),
    )


def build_projection(
    *,
    deployment_registry: CustomerDeploymentRegistry,
    secret_store: CustomerDeploymentSecretStore,
    account_binding_store: (
        TrustedAgentAccountBindingStore
    ),
    credential_registry: (
        TrustedAgentCredentialRegistry
    ),
    execution_signing_key_registry: (
        TrustedAgentSigningKeyRegistry
    ),
    control_signing_key_registry: (
        TrustedAgentSigningKeyRegistry
    ),
    execution_target_registry: (
        ExecutionTargetRegistry
    ),
) -> CustomerDeploymentRuntimeProjection:
    return CustomerDeploymentRuntimeProjection(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        credential_registry=credential_registry,
        execution_signing_key_registry=(
            execution_signing_key_registry
        ),
        control_signing_key_registry=(
            control_signing_key_registry
        ),
        execution_target_registry=(
            execution_target_registry
        ),
    )


def register_complete_deployment(
    *,
    deployment_registry: CustomerDeploymentRegistry,
    secret_store: CustomerDeploymentSecretStore,
    account_binding_store: (
        TrustedAgentAccountBindingStore
    ),
    number: int,
    agent_secret: str | None = None,
    execution_secret: str | None = None,
    control_secret: str | None = None,
) -> CustomerDeploymentSecrets:
    deployment_id = (
        f"deployment-{number:03d}"
    )
    agent_id = (
        f"trusted-agent-{number:03d}"
    )

    deployment_registry.register(
        CustomerDeployment(
            customer_id=(
                f"customer-{number:03d}"
            ),
            deployment_id=deployment_id,
            agent_id=agent_id,
        )
    )

    secrets = CustomerDeploymentSecrets(
        deployment_id=deployment_id,
        agent_secret=(
            agent_secret
            if agent_secret is not None
            else f"agent-secret-{number}"
        ),
        execution_mission_signing_secret=(
            execution_secret
            if execution_secret is not None
            else f"execution-secret-{number}"
        ),
        control_mission_signing_secret=(
            control_secret
            if control_secret is not None
            else f"control-secret-{number}"
        ),
    )

    secret_store.register(
        secrets
    )

    account_binding_store.bind(
        agent_id=agent_id,
        account_fingerprint=(
            f"server-{number}:{1000 + number}"
        ),
    )

    return secrets


def test_complete_deployment_projects_all_runtime_registries(
    tmp_path,
) -> None:
    (
        deployment_registry,
        secret_store,
        account_binding_store,
    ) = build_sources(
        tmp_path
    )

    secrets = register_complete_deployment(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        number=1,
    )

    (
        credential_registry,
        execution_registry,
        control_registry,
        target_registry,
    ) = build_runtime()

    projection = build_projection(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        credential_registry=credential_registry,
        execution_signing_key_registry=(
            execution_registry
        ),
        control_signing_key_registry=(
            control_registry
        ),
        execution_target_registry=target_registry,
    )

    assert projection.project() == 1

    assert (
        credential_registry.get_secret(
            agent_id="trusted-agent-001"
        )
        == secrets.agent_secret
    )

    assert (
        execution_registry.get_secret(
            agent_id="trusted-agent-001"
        )
        ==
        secrets.execution_mission_signing_secret
    )

    assert (
        control_registry.get_secret(
            agent_id="trusted-agent-001"
        )
        ==
        secrets.control_mission_signing_secret
    )

    target = target_registry.get(
        agent_id="trusted-agent-001"
    )

    assert target is not None
    assert (
        target.account_fingerprint
        == "server-1:1001"
    )


def test_multiple_deployments_project_independently(
    tmp_path,
) -> None:
    (
        deployment_registry,
        secret_store,
        account_binding_store,
    ) = build_sources(
        tmp_path
    )

    first = register_complete_deployment(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        number=1,
    )

    second = register_complete_deployment(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        number=2,
    )

    (
        credential_registry,
        execution_registry,
        control_registry,
        target_registry,
    ) = build_runtime()

    projection = build_projection(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        credential_registry=credential_registry,
        execution_signing_key_registry=(
            execution_registry
        ),
        control_signing_key_registry=(
            control_registry
        ),
        execution_target_registry=target_registry,
    )

    assert projection.project() == 2

    assert credential_registry.size() == 2
    assert execution_registry.size() == 2
    assert control_registry.size() == 2
    assert target_registry.size() == 2

    assert (
        credential_registry.get_secret(
            agent_id="trusted-agent-001"
        )
        == first.agent_secret
    )

    assert (
        credential_registry.get_secret(
            agent_id="trusted-agent-002"
        )
        == second.agent_secret
    )

    assert (
        target_registry.get(
            agent_id="trusted-agent-001"
        ).account_fingerprint
        == "server-1:1001"
    )

    assert (
        target_registry.get(
            agent_id="trusted-agent-002"
        ).account_fingerprint
        == "server-2:1002"
    )


def test_repeated_projection_is_idempotent(
    tmp_path,
) -> None:
    (
        deployment_registry,
        secret_store,
        account_binding_store,
    ) = build_sources(
        tmp_path
    )

    register_complete_deployment(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        number=1,
    )

    (
        credential_registry,
        execution_registry,
        control_registry,
        target_registry,
    ) = build_runtime()

    projection = build_projection(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        credential_registry=credential_registry,
        execution_signing_key_registry=(
            execution_registry
        ),
        control_signing_key_registry=(
            control_registry
        ),
        execution_target_registry=target_registry,
    )

    assert projection.project() == 1
    assert projection.project() == 1

    assert credential_registry.size() == 1
    assert execution_registry.size() == 1
    assert control_registry.size() == 1
    assert target_registry.size() == 1


def test_missing_secret_fails_before_runtime_mutation(
    tmp_path,
) -> None:
    (
        deployment_registry,
        secret_store,
        account_binding_store,
    ) = build_sources(
        tmp_path
    )

    register_complete_deployment(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        number=1,
    )

    deployment_registry.register(
        CustomerDeployment(
            customer_id="customer-002",
            deployment_id="deployment-002",
            agent_id="trusted-agent-002",
        )
    )

    account_binding_store.bind(
        agent_id="trusted-agent-002",
        account_fingerprint="server-2:1002",
    )

    (
        credential_registry,
        execution_registry,
        control_registry,
        target_registry,
    ) = build_runtime()

    projection = build_projection(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        credential_registry=credential_registry,
        execution_signing_key_registry=(
            execution_registry
        ),
        control_signing_key_registry=(
            control_registry
        ),
        execution_target_registry=target_registry,
    )

    with pytest.raises(
        RuntimeError,
        match="secret material.*missing",
    ):
        projection.project()

    assert credential_registry.size() == 0
    assert execution_registry.size() == 0
    assert control_registry.size() == 0
    assert target_registry.size() == 0


def test_missing_account_binding_fails_before_runtime_mutation(
    tmp_path,
) -> None:
    (
        deployment_registry,
        secret_store,
        account_binding_store,
    ) = build_sources(
        tmp_path
    )

    register_complete_deployment(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        number=1,
    )

    deployment_registry.register(
        CustomerDeployment(
            customer_id="customer-002",
            deployment_id="deployment-002",
            agent_id="trusted-agent-002",
        )
    )

    secret_store.register(
        CustomerDeploymentSecrets(
            deployment_id="deployment-002",
            agent_secret="agent-secret-2",
            execution_mission_signing_secret=(
                "execution-secret-2"
            ),
            control_mission_signing_secret=(
                "control-secret-2"
            ),
        )
    )

    (
        credential_registry,
        execution_registry,
        control_registry,
        target_registry,
    ) = build_runtime()

    projection = build_projection(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        credential_registry=credential_registry,
        execution_signing_key_registry=(
            execution_registry
        ),
        control_signing_key_registry=(
            control_registry
        ),
        execution_target_registry=target_registry,
    )

    with pytest.raises(
        RuntimeError,
        match="account binding.*missing",
    ):
        projection.project()

    assert credential_registry.size() == 0
    assert execution_registry.size() == 0
    assert control_registry.size() == 0
    assert target_registry.size() == 0


def test_credential_conflict_fails_without_projection_mutation(
    tmp_path,
) -> None:
    (
        deployment_registry,
        secret_store,
        account_binding_store,
    ) = build_sources(
        tmp_path
    )

    register_complete_deployment(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        number=1,
    )

    (
        credential_registry,
        execution_registry,
        control_registry,
        target_registry,
    ) = build_runtime()

    credential_registry.register(
        agent_id="trusted-agent-001",
        agent_secret="conflicting-secret",
    )

    projection = build_projection(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        credential_registry=credential_registry,
        execution_signing_key_registry=(
            execution_registry
        ),
        control_signing_key_registry=(
            control_registry
        ),
        execution_target_registry=target_registry,
    )

    with pytest.raises(
        ValueError,
        match="runtime credential.*conflicts",
    ):
        projection.project()

    assert credential_registry.size() == 1

    assert (
        credential_registry.get_secret(
            agent_id="trusted-agent-001"
        )
        == "conflicting-secret"
    )

    assert execution_registry.size() == 0
    assert control_registry.size() == 0
    assert target_registry.size() == 0


def test_execution_signing_conflict_fails_without_projection_mutation(
    tmp_path,
) -> None:
    (
        deployment_registry,
        secret_store,
        account_binding_store,
    ) = build_sources(
        tmp_path
    )

    register_complete_deployment(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        number=1,
    )

    (
        credential_registry,
        execution_registry,
        control_registry,
        target_registry,
    ) = build_runtime()

    execution_registry.register(
        agent_id="trusted-agent-001",
        signing_secret="conflicting-execution-secret",
    )

    projection = build_projection(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        credential_registry=credential_registry,
        execution_signing_key_registry=(
            execution_registry
        ),
        control_signing_key_registry=(
            control_registry
        ),
        execution_target_registry=target_registry,
    )

    with pytest.raises(
        ValueError,
        match="Execution signing runtime key.*conflicts",
    ):
        projection.project()

    assert credential_registry.size() == 0

    assert execution_registry.size() == 1

    assert (
        execution_registry.get_secret(
            agent_id="trusted-agent-001"
        )
        == "conflicting-execution-secret"
    )

    assert control_registry.size() == 0
    assert target_registry.size() == 0


def test_control_signing_conflict_fails_without_projection_mutation(
    tmp_path,
) -> None:
    (
        deployment_registry,
        secret_store,
        account_binding_store,
    ) = build_sources(
        tmp_path
    )

    register_complete_deployment(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        number=1,
    )

    (
        credential_registry,
        execution_registry,
        control_registry,
        target_registry,
    ) = build_runtime()

    control_registry.register(
        agent_id="trusted-agent-001",
        signing_secret="conflicting-control-secret",
    )

    projection = build_projection(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        credential_registry=credential_registry,
        execution_signing_key_registry=(
            execution_registry
        ),
        control_signing_key_registry=(
            control_registry
        ),
        execution_target_registry=target_registry,
    )

    with pytest.raises(
        ValueError,
        match="Control signing runtime key.*conflicts",
    ):
        projection.project()

    assert credential_registry.size() == 0
    assert execution_registry.size() == 0

    assert control_registry.size() == 1

    assert (
        control_registry.get_secret(
            agent_id="trusted-agent-001"
        )
        == "conflicting-control-secret"
    )

    assert target_registry.size() == 0


def test_execution_target_conflict_fails_without_projection_mutation(
    tmp_path,
) -> None:
    (
        deployment_registry,
        secret_store,
        account_binding_store,
    ) = build_sources(
        tmp_path
    )

    register_complete_deployment(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        number=1,
    )

    (
        credential_registry,
        execution_registry,
        control_registry,
        target_registry,
    ) = build_runtime()

    conflicting_target = ExecutionTarget(
        agent_id="trusted-agent-001",
        account_fingerprint="different-server:9999",
    )

    target_registry.register(
        conflicting_target
    )

    projection = build_projection(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        credential_registry=credential_registry,
        execution_signing_key_registry=(
            execution_registry
        ),
        control_signing_key_registry=(
            control_registry
        ),
        execution_target_registry=target_registry,
    )

    with pytest.raises(
        ValueError,
        match="Execution target.*conflicts",
    ):
        projection.project()

    assert credential_registry.size() == 0
    assert execution_registry.size() == 0
    assert control_registry.size() == 0
    assert target_registry.size() == 1

    assert (
        target_registry.get(
            agent_id="trusted-agent-001"
        )
        == conflicting_target
    )


def test_execution_and_control_signing_domains_must_be_separate(
    tmp_path,
) -> None:
    (
        deployment_registry,
        secret_store,
        account_binding_store,
    ) = build_sources(
        tmp_path
    )

    credential_registry = (
        TrustedAgentCredentialRegistry()
    )

    shared_signing_registry = (
        TrustedAgentSigningKeyRegistry()
    )

    target_registry = ExecutionTargetRegistry()

    with pytest.raises(
        ValueError,
        match="separate security domains",
    ):
        CustomerDeploymentRuntimeProjection(
            deployment_registry=deployment_registry,
            secret_store=secret_store,
            account_binding_store=(
                account_binding_store
            ),
            credential_registry=credential_registry,
            execution_signing_key_registry=(
                shared_signing_registry
            ),
            control_signing_key_registry=(
                shared_signing_registry
            ),
            execution_target_registry=target_registry,
        )


def test_projection_preserves_opaque_secrets_exactly(
    tmp_path,
) -> None:
    (
        deployment_registry,
        secret_store,
        account_binding_store,
    ) = build_sources(
        tmp_path
    )

    secrets = register_complete_deployment(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        number=1,
        agent_secret="  agent-秘密-secret  ",
        execution_secret=(
            "\texecution-αβγ-secret\n"
        ),
        control_secret=(
            " control-密钥-secret "
        ),
    )

    (
        credential_registry,
        execution_registry,
        control_registry,
        target_registry,
    ) = build_runtime()

    projection = build_projection(
        deployment_registry=deployment_registry,
        secret_store=secret_store,
        account_binding_store=(
            account_binding_store
        ),
        credential_registry=credential_registry,
        execution_signing_key_registry=(
            execution_registry
        ),
        control_signing_key_registry=(
            control_registry
        ),
        execution_target_registry=target_registry,
    )

    assert projection.project() == 1

    assert (
        credential_registry.get_secret(
            agent_id="trusted-agent-001"
        )
        == secrets.agent_secret
    )

    assert (
        execution_registry.get_secret(
            agent_id="trusted-agent-001"
        )
        ==
        secrets.execution_mission_signing_secret
    )

    assert (
        control_registry.get_secret(
            agent_id="trusted-agent-001"
        )
        ==
        secrets.control_mission_signing_secret
    )