"""
TODOBA Customer Deployment Enrollment Service Tests

Proof:
- complete durable enrollment
- identical retry is idempotent
- secret conflict fails closed
- account binding conflict fails closed
- deployment identity conflict fails closed
- runtime conflict must fail before durable activation
- successful enrollment becomes available in runtime projection

All persistence in this suite is isolated beneath tmp_path.
"""

from pathlib import Path

import pytest

from backend.commercial.customer_deployment_enrollment_service import (
    CustomerDeploymentEnrollmentService,
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


MASTER_KEY = b"T" * 32


def build_enrollment_system(
    tmp_path: Path,
):
    deployment_registry = (
        CustomerDeploymentRegistry(
            tmp_path
            / "customer_deployments.json"
        )
    )

    deployment_registry.initialize_empty()

    secret_store = (
        CustomerDeploymentSecretStore(
            tmp_path
            / "customer_deployment_secrets.json",
            master_key=MASTER_KEY,
        )
    )

    secret_store.initialize_empty()

    account_binding_store = (
        TrustedAgentAccountBindingStore(
            tmp_path
            / "trusted_agent_account_bindings.json"
        )
    )

    account_binding_store.initialize_empty()

    credential_registry = (
        TrustedAgentCredentialRegistry()
    )

    execution_signing_key_registry = (
        TrustedAgentSigningKeyRegistry()
    )

    control_signing_key_registry = (
        TrustedAgentSigningKeyRegistry()
    )

    execution_target_registry = (
        ExecutionTargetRegistry()
    )

    runtime_projection = (
        CustomerDeploymentRuntimeProjection(
            deployment_registry=(
                deployment_registry
            ),
            secret_store=secret_store,
            account_binding_store=(
                account_binding_store
            ),
            credential_registry=(
                credential_registry
            ),
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
    )

    service = (
        CustomerDeploymentEnrollmentService(
            deployment_registry=(
                deployment_registry
            ),
            secret_store=secret_store,
            account_binding_store=(
                account_binding_store
            ),
            runtime_projection=(
                runtime_projection
            ),
        )
    )

    return {
        "service": service,
        "deployment_registry": (
            deployment_registry
        ),
        "secret_store": secret_store,
        "account_binding_store": (
            account_binding_store
        ),
        "credential_registry": (
            credential_registry
        ),
        "execution_signing_key_registry": (
            execution_signing_key_registry
        ),
        "control_signing_key_registry": (
            control_signing_key_registry
        ),
        "execution_target_registry": (
            execution_target_registry
        ),
        "runtime_projection": (
            runtime_projection
        ),
    }


def make_deployment(
    *,
    customer_id: str = "customer-001",
    deployment_id: str = "deployment-001",
    agent_id: str = "trusted-agent-001",
) -> CustomerDeployment:
    return CustomerDeployment(
        customer_id=customer_id,
        deployment_id=deployment_id,
        agent_id=agent_id,
    )


def make_secrets(
    *,
    deployment_id: str = "deployment-001",
    suffix: str = "a",
) -> CustomerDeploymentSecrets:
    return CustomerDeploymentSecrets(
        deployment_id=deployment_id,
        agent_secret=(
            f"agent-secret-{suffix}"
        ),
        execution_mission_signing_secret=(
            f"execution-secret-{suffix}"
        ),
        control_mission_signing_secret=(
            f"control-secret-{suffix}"
        ),
    )


def test_complete_enrollment_is_durable_and_projected(
    tmp_path: Path,
) -> None:
    context = build_enrollment_system(
        tmp_path
    )

    deployment = make_deployment()
    secrets = make_secrets()

    result = context[
        "service"
    ].enroll(
        deployment=deployment,
        secrets=secrets,
        account_fingerprint="account-a",
    )

    assert result.deployment == deployment
    assert (
        result.account_fingerprint
        == "account-a"
    )
    assert (
        result.projected_deployment_count
        == 1
    )

    assert (
        context[
            "deployment_registry"
        ].get(
            deployment_id="deployment-001"
        )
        == deployment
    )

    stored_secrets = context[
        "secret_store"
    ].get(
        deployment_id="deployment-001"
    )

    assert stored_secrets is not None
    assert stored_secrets.same_secret_material(
        secrets
    )

    assert context[
        "account_binding_store"
    ].owns_account(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    assert (
        context[
            "credential_registry"
        ].get_secret(
            agent_id="trusted-agent-001"
        )
        == "agent-secret-a"
    )

    assert (
        context[
            "execution_signing_key_registry"
        ].get_secret(
            agent_id="trusted-agent-001"
        )
        == "execution-secret-a"
    )

    assert (
        context[
            "control_signing_key_registry"
        ].get_secret(
            agent_id="trusted-agent-001"
        )
        == "control-secret-a"
    )

    target = context[
        "execution_target_registry"
    ].get(
        agent_id="trusted-agent-001"
    )

    assert target is not None
    assert target.account_fingerprint == (
        "account-a"
    )


def test_identical_enrollment_retry_is_idempotent(
    tmp_path: Path,
) -> None:
    context = build_enrollment_system(
        tmp_path
    )

    deployment = make_deployment()
    secrets = make_secrets()

    first = context[
        "service"
    ].enroll(
        deployment=deployment,
        secrets=secrets,
        account_fingerprint="account-a",
    )

    second = context[
        "service"
    ].enroll(
        deployment=deployment,
        secrets=secrets,
        account_fingerprint="account-a",
    )

    assert first == second

    assert context[
        "deployment_registry"
    ].size() == 1

    assert context[
        "execution_target_registry"
    ].size() == 1

    restored_registry = (
        CustomerDeploymentRegistry(
            tmp_path
            / "customer_deployments.json"
        )
    )

    restored_secret_store = (
        CustomerDeploymentSecretStore(
            tmp_path
            / "customer_deployment_secrets.json",
            master_key=MASTER_KEY,
        )
    )

    restored_binding_store = (
        TrustedAgentAccountBindingStore(
            tmp_path
            / "trusted_agent_account_bindings.json"
        )
    )

    assert restored_registry.size() == 1

    restored_secrets = (
        restored_secret_store.get(
            deployment_id="deployment-001"
        )
    )

    assert restored_secrets is not None
    assert restored_secrets.same_secret_material(
        secrets
    )

    assert restored_binding_store.owns_account(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )


def test_secret_conflict_fails_before_activation(
    tmp_path: Path,
) -> None:
    context = build_enrollment_system(
        tmp_path
    )

    conflicting = make_secrets(
        suffix="existing"
    )

    context[
        "secret_store"
    ].register(
        conflicting
    )

    with pytest.raises(
        ValueError,
        match="secret material",
    ):
        context[
            "service"
        ].enroll(
            deployment=make_deployment(),
            secrets=make_secrets(
                suffix="candidate"
            ),
            account_fingerprint=(
                "account-a"
            ),
        )

    assert context[
        "deployment_registry"
    ].size() == 0

    assert (
        context[
            "account_binding_store"
        ].get_account_fingerprint(
            agent_id="trusted-agent-001"
        )
        is None
    )

    stored = context[
        "secret_store"
    ].get(
        deployment_id="deployment-001"
    )

    assert stored is not None
    assert stored.same_secret_material(
        conflicting
    )

    assert (
        context[
            "execution_target_registry"
        ].get(
            agent_id="trusted-agent-001"
        )
        is None
    )


def test_account_binding_conflict_fails_before_activation(
    tmp_path: Path,
) -> None:
    context = build_enrollment_system(
        tmp_path
    )

    context[
        "account_binding_store"
    ].bind(
        agent_id="trusted-agent-001",
        account_fingerprint=(
            "account-original"
        ),
    )

    with pytest.raises(
        ValueError,
        match="account binding",
    ):
        context[
            "service"
        ].enroll(
            deployment=make_deployment(),
            secrets=make_secrets(),
            account_fingerprint=(
                "account-candidate"
            ),
        )

    assert context[
        "deployment_registry"
    ].size() == 0

    assert (
        context[
            "secret_store"
        ].get(
            deployment_id="deployment-001"
        )
        is None
    )

    assert (
        context[
            "account_binding_store"
        ].get_account_fingerprint(
            agent_id="trusted-agent-001"
        )
        == "account-original"
    )

    assert (
        context[
            "execution_target_registry"
        ].get(
            agent_id="trusted-agent-001"
        )
        is None
    )


def test_deployment_identity_conflict_fails_before_staging(
    tmp_path: Path,
) -> None:
    context = build_enrollment_system(
        tmp_path
    )

    existing = make_deployment(
        customer_id="customer-existing",
        deployment_id="deployment-001",
        agent_id="trusted-agent-existing",
    )

    context[
        "deployment_registry"
    ].register(
        existing
    )

    with pytest.raises(
        ValueError,
        match="existing deployment",
    ):
        context[
            "service"
        ].enroll(
            deployment=make_deployment(
                customer_id="customer-candidate",
                deployment_id="deployment-001",
                agent_id="trusted-agent-001",
            ),
            secrets=make_secrets(),
            account_fingerprint="account-a",
        )

    assert (
        context[
            "deployment_registry"
        ].get(
            deployment_id="deployment-001"
        )
        == existing
    )

    assert (
        context[
            "secret_store"
        ].get(
            deployment_id="deployment-001"
        )
        is None
    )

    assert (
        context[
            "account_binding_store"
        ].get_account_fingerprint(
            agent_id="trusted-agent-001"
        )
        is None
    )


def test_runtime_conflict_must_fail_before_durable_activation(
    tmp_path: Path,
) -> None:
    context = build_enrollment_system(
        tmp_path
    )

    context[
        "credential_registry"
    ].register(
        agent_id="trusted-agent-001",
        agent_secret=(
            "conflicting-runtime-secret"
        ),
    )

    with pytest.raises(
        ValueError,
        match="runtime credential",
    ):
        context[
            "service"
        ].enroll(
            deployment=make_deployment(),
            secrets=make_secrets(),
            account_fingerprint="account-a",
        )

    # A runtime conflict must never leave a commercial
    # deployment activated or partially staged.
    assert context[
        "deployment_registry"
    ].size() == 0

    assert (
        context[
            "secret_store"
        ].get(
            deployment_id="deployment-001"
        )
        is None
    )

    assert (
        context[
            "account_binding_store"
        ].get_account_fingerprint(
            agent_id="trusted-agent-001"
        )
        is None
    )

    assert (
        context[
            "execution_target_registry"
        ].get(
            agent_id="trusted-agent-001"
        )
        is None
    )

def test_prepare_stages_without_activation_or_runtime_projection(
    tmp_path: Path,
) -> None:
    context = build_enrollment_system(
        tmp_path
    )

    deployment = make_deployment()
    secrets = make_secrets()

    result = context[
        "service"
    ].prepare(
        deployment=deployment,
        secrets=secrets,
        account_fingerprint="account-a",
    )

    assert result.deployment == deployment
    assert (
        result.account_fingerprint
        == "account-a"
    )

    assert context[
        "deployment_registry"
    ].size() == 0

    stored_secrets = context[
        "secret_store"
    ].get(
        deployment_id="deployment-001"
    )

    assert stored_secrets is not None
    assert stored_secrets.same_secret_material(
        secrets
    )

    assert context[
        "account_binding_store"
    ].owns_account(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    assert (
        context[
            "execution_target_registry"
        ].get(
            agent_id="trusted-agent-001"
        )
        is None
    )

    assert (
        context[
            "credential_registry"
        ].get_secret(
            agent_id="trusted-agent-001"
        )
        is None
    )

    assert (
        context[
            "execution_signing_key_registry"
        ].get_secret(
            agent_id="trusted-agent-001"
        )
        is None
    )

    assert (
        context[
            "control_signing_key_registry"
        ].get_secret(
            agent_id="trusted-agent-001"
        )
        is None
    )


def test_identical_prepare_retry_is_idempotent_without_activation(
    tmp_path: Path,
) -> None:
    context = build_enrollment_system(
        tmp_path
    )

    deployment = make_deployment()
    secrets = make_secrets()

    first = context[
        "service"
    ].prepare(
        deployment=deployment,
        secrets=secrets,
        account_fingerprint="account-a",
    )

    second = context[
        "service"
    ].prepare(
        deployment=deployment,
        secrets=secrets,
        account_fingerprint="account-a",
    )

    assert first == second

    assert context[
        "deployment_registry"
    ].size() == 0

    assert (
        context[
            "execution_target_registry"
        ].size()
        == 0
    )

    restored_secret_store = (
        CustomerDeploymentSecretStore(
            tmp_path
            / "customer_deployment_secrets.json",
            master_key=MASTER_KEY,
        )
    )

    restored_binding_store = (
        TrustedAgentAccountBindingStore(
            tmp_path
            / "trusted_agent_account_bindings.json"
        )
    )

    restored_secrets = (
        restored_secret_store.get(
            deployment_id="deployment-001"
        )
    )

    assert restored_secrets is not None
    assert restored_secrets.same_secret_material(
        secrets
    )

    assert restored_binding_store.owns_account(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )


def test_activate_without_prepare_fails_closed(
    tmp_path: Path,
) -> None:
    context = build_enrollment_system(
        tmp_path
    )

    with pytest.raises(
        RuntimeError,
        match="secret material is missing",
    ):
        context[
            "service"
        ].activate(
            deployment=make_deployment(),
            secrets=make_secrets(),
            account_fingerprint="account-a",
        )

    assert context[
        "deployment_registry"
    ].size() == 0

    assert (
        context[
            "secret_store"
        ].get(
            deployment_id="deployment-001"
        )
        is None
    )

    assert (
        context[
            "account_binding_store"
        ].get_account_fingerprint(
            agent_id="trusted-agent-001"
        )
        is None
    )

    assert (
        context[
            "execution_target_registry"
        ].get(
            agent_id="trusted-agent-001"
        )
        is None
    )


def test_activate_prepared_candidate_crosses_activation_barrier(
    tmp_path: Path,
) -> None:
    context = build_enrollment_system(
        tmp_path
    )

    deployment = make_deployment()
    secrets = make_secrets()

    context[
        "service"
    ].prepare(
        deployment=deployment,
        secrets=secrets,
        account_fingerprint="account-a",
    )

    assert context[
        "deployment_registry"
    ].size() == 0

    assert (
        context[
            "execution_target_registry"
        ].get(
            agent_id="trusted-agent-001"
        )
        is None
    )

    result = context[
        "service"
    ].activate(
        deployment=deployment,
        secrets=secrets,
        account_fingerprint="account-a",
    )

    assert result.deployment == deployment
    assert (
        result.projected_deployment_count
        == 1
    )

    assert (
        context[
            "deployment_registry"
        ].get(
            deployment_id="deployment-001"
        )
        == deployment
    )

    target = context[
        "execution_target_registry"
    ].get(
        agent_id="trusted-agent-001"
    )

    assert target is not None
    assert (
        target.account_fingerprint
        == "account-a"
    )

    assert (
        context[
            "credential_registry"
        ].get_secret(
            agent_id="trusted-agent-001"
        )
        == "agent-secret-a"
    )

    assert (
        context[
            "execution_signing_key_registry"
        ].get_secret(
            agent_id="trusted-agent-001"
        )
        == "execution-secret-a"
    )

    assert (
        context[
            "control_signing_key_registry"
        ].get_secret(
            agent_id="trusted-agent-001"
        )
        == "control-secret-a"
    )


def test_activate_revalidates_runtime_conflict_after_prepare(
    tmp_path: Path,
) -> None:
    context = build_enrollment_system(
        tmp_path
    )

    deployment = make_deployment()
    secrets = make_secrets()

    context[
        "service"
    ].prepare(
        deployment=deployment,
        secrets=secrets,
        account_fingerprint="account-a",
    )

    context[
        "credential_registry"
    ].register(
        agent_id="trusted-agent-001",
        agent_secret=(
            "conflicting-runtime-secret"
        ),
    )

    with pytest.raises(
        ValueError,
        match="runtime credential",
    ):
        context[
            "service"
        ].activate(
            deployment=deployment,
            secrets=secrets,
            account_fingerprint="account-a",
        )

    assert context[
        "deployment_registry"
    ].size() == 0

    stored_secrets = context[
        "secret_store"
    ].get(
        deployment_id="deployment-001"
    )

    assert stored_secrets is not None
    assert stored_secrets.same_secret_material(
        secrets
    )

    assert context[
        "account_binding_store"
    ].owns_account(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    assert (
        context[
            "execution_target_registry"
        ].get(
            agent_id="trusted-agent-001"
        )
        is None
    )
