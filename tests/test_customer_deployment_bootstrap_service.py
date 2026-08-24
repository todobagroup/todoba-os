"""
TODOBA Customer Deployment Bootstrap Service Tests

Proof:
- complete bootstrap creates one commercial deployment
- identical request retry is idempotent
- duplicate customer click converges on one deployment
- restart recovers identical durable identity and secrets
- partial secret staging recovers without rotating secrets
- partial secret + binding staging recovers safely
- existing commercial deployment is adopted
- cross-customer MT5 reuse fails closed
- request identity cannot move to another account
- bootstrap persistence never stores raw account or secrets
- orphan account binding cannot become a second deployment

All persistence is isolated beneath pytest tmp_path.
"""

import hashlib
from pathlib import Path

import pytest

from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapRecord,
    CustomerDeploymentBootstrapService,
    CustomerDeploymentBootstrapStore,
)
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


MASTER_KEY = b"B" * 32


def account_digest(
    account_fingerprint: str,
) -> str:
    return hashlib.sha256(
        account_fingerprint.encode(
            "utf-8"
        )
    ).hexdigest()


def build_system(
    root: Path,
):
    deployment_registry = (
        CustomerDeploymentRegistry(
            root
            / "customer_deployments.json"
        )
    )
    deployment_registry.initialize_empty()

    secret_store = (
        CustomerDeploymentSecretStore(
            root
            / "customer_deployment_secrets.json",
            master_key=MASTER_KEY,
        )
    )
    secret_store.initialize_empty()

    account_binding_store = (
        TrustedAgentAccountBindingStore(
            root
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

    enrollment_service = (
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

    bootstrap_store = (
        CustomerDeploymentBootstrapStore(
            root
            / "customer_deployment_bootstraps.json"
        )
    )
    bootstrap_store.initialize_empty()

    bootstrap_service = (
        CustomerDeploymentBootstrapService(
            bootstrap_store=bootstrap_store,
            deployment_registry=(
                deployment_registry
            ),
            secret_store=secret_store,
            account_binding_store=(
                account_binding_store
            ),
            enrollment_service=(
                enrollment_service
            ),
        )
    )

    return {
        "bootstrap_service": (
            bootstrap_service
        ),
        "bootstrap_store": (
            bootstrap_store
        ),
        "deployment_registry": (
            deployment_registry
        ),
        "secret_store": (
            secret_store
        ),
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
        "enrollment_service": (
            enrollment_service
        ),
    }


def seed_bootstrap_record(
    context,
    *,
    enrollment_request_id: str = "request-001",
    customer_id: str = "customer-001",
    deployment_id: str = "deployment-recovery",
    agent_id: str = "trusted-agent-recovery",
    account_fingerprint: str = "account-a",
) -> CustomerDeploymentBootstrapRecord:
    record = (
        CustomerDeploymentBootstrapRecord(
            enrollment_request_id=(
                enrollment_request_id
            ),
            customer_id=customer_id,
            deployment_id=deployment_id,
            agent_id=agent_id,
            account_fingerprint_digest=(
                account_digest(
                    account_fingerprint
                )
            ),
        )
    )

    context[
        "bootstrap_store"
    ].register(
        record
    )

    return record


def make_staged_secrets(
    *,
    deployment_id: str = "deployment-recovery",
) -> CustomerDeploymentSecrets:
    return CustomerDeploymentSecrets(
        deployment_id=deployment_id,
        agent_secret=(
            "staged-agent-secret"
        ),
        execution_mission_signing_secret=(
            "staged-execution-secret"
        ),
        control_mission_signing_secret=(
            "staged-control-secret"
        ),
    )


def test_complete_bootstrap_creates_one_commercial_deployment(
    tmp_path: Path,
) -> None:
    context = build_system(
        tmp_path
    )

    result = context[
        "bootstrap_service"
    ].bootstrap(
        enrollment_request_id="request-001",
        customer_id="customer-001",
        account_fingerprint="account-a",
    )

    assert context[
        "bootstrap_store"
    ].size() == 1

    assert context[
        "deployment_registry"
    ].size() == 1

    assert (
        result.deployment.customer_id
        == "customer-001"
    )

    assert context[
        "account_binding_store"
    ].owns_account(
        agent_id=(
            result.deployment.agent_id
        ),
        account_fingerprint="account-a",
    )

    stored_secrets = context[
        "secret_store"
    ].get(
        deployment_id=(
            result.deployment.deployment_id
        )
    )

    assert stored_secrets is not None

    assert stored_secrets.same_secret_material(
        result.secrets
    )

    target = context[
        "execution_target_registry"
    ].get(
        agent_id=(
            result.deployment.agent_id
        )
    )

    assert target is not None
    assert (
        target.account_fingerprint
        == "account-a"
    )


def test_identical_request_retry_is_idempotent(
    tmp_path: Path,
) -> None:
    context = build_system(
        tmp_path
    )

    first = context[
        "bootstrap_service"
    ].bootstrap(
        enrollment_request_id="request-001",
        customer_id="customer-001",
        account_fingerprint="account-a",
    )

    retry = context[
        "bootstrap_service"
    ].bootstrap(
        enrollment_request_id="request-001",
        customer_id="customer-001",
        account_fingerprint="account-a",
    )

    assert (
        first.deployment
        == retry.deployment
    )

    assert first.secrets.same_secret_material(
        retry.secrets
    )

    assert context[
        "bootstrap_store"
    ].size() == 1

    assert context[
        "deployment_registry"
    ].size() == 1


def test_duplicate_customer_click_converges_on_existing_account(
    tmp_path: Path,
) -> None:
    context = build_system(
        tmp_path
    )

    first = context[
        "bootstrap_service"
    ].bootstrap(
        enrollment_request_id="request-001",
        customer_id="customer-001",
        account_fingerprint="account-a",
    )

    duplicate = context[
        "bootstrap_service"
    ].bootstrap(
        enrollment_request_id="request-002",
        customer_id="customer-001",
        account_fingerprint="account-a",
    )

    assert (
        first.deployment
        == duplicate.deployment
    )

    assert first.secrets.same_secret_material(
        duplicate.secrets
    )

    assert context[
        "bootstrap_store"
    ].size() == 1

    assert context[
        "deployment_registry"
    ].size() == 1


def test_restart_recovers_same_identity_and_secret_material(
    tmp_path: Path,
) -> None:
    first_context = build_system(
        tmp_path
    )

    first = first_context[
        "bootstrap_service"
    ].bootstrap(
        enrollment_request_id="request-001",
        customer_id="customer-001",
        account_fingerprint="account-a",
    )

    restarted = build_system(
        tmp_path
    )

    recovered = restarted[
        "bootstrap_service"
    ].bootstrap(
        enrollment_request_id="request-001",
        customer_id="customer-001",
        account_fingerprint="account-a",
    )

    assert (
        recovered.deployment
        == first.deployment
    )

    assert recovered.secrets.same_secret_material(
        first.secrets
    )

    assert restarted[
        "bootstrap_store"
    ].size() == 1

    assert restarted[
        "deployment_registry"
    ].size() == 1

    assert restarted[
        "account_binding_store"
    ].owns_account(
        agent_id=(
            first.deployment.agent_id
        ),
        account_fingerprint="account-a",
    )


def test_recovery_reuses_secret_staged_before_enrollment(
    tmp_path: Path,
) -> None:
    context = build_system(
        tmp_path
    )

    record = seed_bootstrap_record(
        context
    )

    staged = make_staged_secrets()

    context[
        "secret_store"
    ].register(
        staged
    )

    assert context[
        "deployment_registry"
    ].size() == 0

    assert (
        context[
            "account_binding_store"
        ].get_account_fingerprint(
            agent_id=record.agent_id
        )
        is None
    )

    recovered = context[
        "bootstrap_service"
    ].bootstrap(
        enrollment_request_id="request-001",
        customer_id="customer-001",
        account_fingerprint="account-a",
    )

    assert (
        recovered.deployment.deployment_id
        == record.deployment_id
    )

    assert (
        recovered.deployment.agent_id
        == record.agent_id
    )

    assert recovered.secrets.same_secret_material(
        staged
    )

    assert context[
        "deployment_registry"
    ].size() == 1

    assert context[
        "account_binding_store"
    ].owns_account(
        agent_id=record.agent_id,
        account_fingerprint="account-a",
    )


def test_recovery_from_staged_secret_and_binding_completes_activation(
    tmp_path: Path,
) -> None:
    context = build_system(
        tmp_path
    )

    record = seed_bootstrap_record(
        context
    )

    staged = make_staged_secrets()

    context[
        "secret_store"
    ].register(
        staged
    )

    context[
        "account_binding_store"
    ].bind(
        agent_id=record.agent_id,
        account_fingerprint="account-a",
    )

    assert context[
        "deployment_registry"
    ].size() == 0

    recovered = context[
        "bootstrap_service"
    ].bootstrap(
        enrollment_request_id="request-001",
        customer_id="customer-001",
        account_fingerprint="account-a",
    )

    assert (
        recovered.deployment.deployment_id
        == record.deployment_id
    )

    assert recovered.secrets.same_secret_material(
        staged
    )

    assert context[
        "deployment_registry"
    ].size() == 1

    assert context[
        "account_binding_store"
    ].owns_account(
        agent_id=record.agent_id,
        account_fingerprint="account-a",
    )


def test_existing_commercial_deployment_is_adopted_without_duplication(
    tmp_path: Path,
) -> None:
    context = build_system(
        tmp_path
    )

    deployment = CustomerDeployment(
        customer_id="customer-001",
        deployment_id=(
            "legacy-deployment-001"
        ),
        agent_id=(
            "legacy-trusted-agent-001"
        ),
    )

    secrets = CustomerDeploymentSecrets(
        deployment_id=(
            deployment.deployment_id
        ),
        agent_secret="legacy-agent-secret",
        execution_mission_signing_secret=(
            "legacy-execution-secret"
        ),
        control_mission_signing_secret=(
            "legacy-control-secret"
        ),
    )

    context[
        "enrollment_service"
    ].enroll(
        deployment=deployment,
        secrets=secrets,
        account_fingerprint="account-a",
    )

    assert context[
        "bootstrap_store"
    ].size() == 0

    adopted = context[
        "bootstrap_service"
    ].bootstrap(
        enrollment_request_id=(
            "request-adopt-001"
        ),
        customer_id="customer-001",
        account_fingerprint="account-a",
    )

    assert (
        adopted.deployment
        == deployment
    )

    assert adopted.secrets.same_secret_material(
        secrets
    )

    assert context[
        "deployment_registry"
    ].size() == 1

    assert context[
        "bootstrap_store"
    ].size() == 1


def test_cross_customer_account_reuse_fails_closed(
    tmp_path: Path,
) -> None:
    context = build_system(
        tmp_path
    )

    original = context[
        "bootstrap_service"
    ].bootstrap(
        enrollment_request_id="request-001",
        customer_id="customer-001",
        account_fingerprint="account-a",
    )

    with pytest.raises(
        ValueError,
        match=(
            "another customer|different customer"
        ),
    ):
        context[
            "bootstrap_service"
        ].bootstrap(
            enrollment_request_id="request-002",
            customer_id="customer-002",
            account_fingerprint="account-a",
        )

    assert context[
        "deployment_registry"
    ].size() == 1

    assert context[
        "bootstrap_store"
    ].size() == 1

    assert context[
        "account_binding_store"
    ].owns_account(
        agent_id=(
            original.deployment.agent_id
        ),
        account_fingerprint="account-a",
    )


def test_enrollment_request_cannot_move_to_another_account(
    tmp_path: Path,
) -> None:
    context = build_system(
        tmp_path
    )

    original = context[
        "bootstrap_service"
    ].bootstrap(
        enrollment_request_id="request-001",
        customer_id="customer-001",
        account_fingerprint="account-a",
    )

    with pytest.raises(
        ValueError,
        match="different MT5 account",
    ):
        context[
            "bootstrap_service"
        ].bootstrap(
            enrollment_request_id="request-001",
            customer_id="customer-001",
            account_fingerprint="account-b",
        )

    assert context[
        "deployment_registry"
    ].size() == 1

    assert context[
        "bootstrap_store"
    ].size() == 1

    assert context[
        "account_binding_store"
    ].owns_account(
        agent_id=(
            original.deployment.agent_id
        ),
        account_fingerprint="account-a",
    )


def test_bootstrap_persistence_and_repr_do_not_expose_raw_sensitive_material(
    tmp_path: Path,
) -> None:
    context = build_system(
        tmp_path
    )

    result = context[
        "bootstrap_service"
    ].bootstrap(
        enrollment_request_id="request-001",
        customer_id="customer-001",
        account_fingerprint=(
            "sensitive-account-fingerprint"
        ),
    )

    bootstrap_text = (
        tmp_path
        / "customer_deployment_bootstraps.json"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "sensitive-account-fingerprint"
        not in bootstrap_text
    )

    assert (
        result.secrets.agent_secret
        not in bootstrap_text
    )

    assert (
        result.secrets
        .execution_mission_signing_secret
        not in bootstrap_text
    )

    assert (
        result.secrets
        .control_mission_signing_secret
        not in bootstrap_text
    )

    rendered = repr(
        result
    )

    assert (
        "sensitive-account-fingerprint"
        not in rendered
    )

    assert (
        result.secrets.agent_secret
        not in rendered
    )

    assert (
        result.secrets
        .execution_mission_signing_secret
        not in rendered
    )

    assert (
        result.secrets
        .control_mission_signing_secret
        not in rendered
    )


def test_orphan_account_binding_cannot_create_second_agent_ownership(
    tmp_path: Path,
) -> None:
    context = build_system(
        tmp_path
    )

    context[
        "account_binding_store"
    ].bind(
        agent_id="orphan-trusted-agent",
        account_fingerprint="account-a",
    )

    with pytest.raises(
        (
            ValueError,
            RuntimeError,
        ),
    ):
        context[
            "bootstrap_service"
        ].bootstrap(
            enrollment_request_id="request-001",
            customer_id="customer-001",
            account_fingerprint="account-a",
        )

    # Existing authoritative binding must survive and no
    # second commercial/bootstrap ownership may appear.
    assert context[
        "account_binding_store"
    ].owns_account(
        agent_id="orphan-trusted-agent",
        account_fingerprint="account-a",
    )

    assert context[
        "bootstrap_store"
    ].size() == 0

    assert context[
        "deployment_registry"
    ].size() == 0
