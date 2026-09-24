import inspect

import pytest

from backend.commercial.customer_legacy_deployment_execution_authorizer import (
    CustomerLegacyDeploymentExecutionAuthorizer,
)
from backend.commercial.customer_deployment_entitlement_authorizer import (
    CustomerDeploymentEntitlementAuthorizer,
)
from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlementRegistry,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_legacy_execution_compatibility_registry import (
    CustomerLegacyExecutionCompatibilityRecord,
    CustomerLegacyExecutionCompatibilityRegistry,
)
from backend.trading.execution.trusted_agent_account_binding_guard import (
    TrustedAgentAccountBindingGuard,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


def test_active_legacy_deployment_with_authoritative_account_is_authorized(
    tmp_path,
) -> None:
    deployment_registry = CustomerDeploymentRegistry(
        tmp_path / "customer_deployments.json"
    )
    deployment_registry.initialize_empty()

    deployment = CustomerDeployment(
        customer_id="customer-001",
        deployment_id="deployment-001",
        agent_id="trusted-agent-001",
    )
    deployment_registry.register(
        deployment
    )

    compatibility_registry = (
        CustomerLegacyExecutionCompatibilityRegistry(
            tmp_path / "legacy_execution_compatibility.json",
            deployment_registry=deployment_registry,
        )
    )
    compatibility_registry.initialize_empty()
    compatibility_registry.register(
        CustomerLegacyExecutionCompatibilityRecord(
            deployment_id=deployment.deployment_id,
            setup_activation_id="setup-activation-001",
            recovery_request_id=(
                "setup-continuity-recovery:deployment-001"
            ),
        )
    )

    entitlement_registry = CustomerDeploymentEntitlementRegistry(
        tmp_path / "customer_deployment_entitlements.json",
        deployment_registry=deployment_registry,
    )
    entitlement_registry.initialize_empty()
    entitlement_registry.activate(
        deployment_id=deployment.deployment_id
    )

    entitlement_authorizer = CustomerDeploymentEntitlementAuthorizer(
        entitlement_registry=entitlement_registry,
    )

    binding_store = TrustedAgentAccountBindingStore(
        tmp_path / "trusted_agent_account_bindings.json"
    )
    binding_store.initialize_empty()
    binding_store.bind(
        agent_id="trusted-agent-001",
        account_fingerprint="Broker-A:123456",
    )

    binding_guard = TrustedAgentAccountBindingGuard(
        binding_store
    )

    authorizer = CustomerLegacyDeploymentExecutionAuthorizer(
        deployment_registry=deployment_registry,
        compatibility_registry=compatibility_registry,
        entitlement_authorizer=entitlement_authorizer,
        account_binding_guard=binding_guard,
    )

    result = authorizer.authorize(
        agent_id="trusted-agent-001",
        account_fingerprint="Broker-A:123456",
    )

    assert result is deployment


def _build_authorizer(
    tmp_path,
    *,
    activate_entitlement: bool = True,
    eligible: bool = True,
):
    deployment_registry = CustomerDeploymentRegistry(
        tmp_path / "deployments.json"
    )
    deployment_registry.initialize_empty()

    deployment = CustomerDeployment(
        customer_id="customer-001",
        deployment_id="deployment-001",
        agent_id="trusted-agent-001",
    )
    deployment_registry.register(deployment)

    compatibility_registry = (
        CustomerLegacyExecutionCompatibilityRegistry(
            tmp_path / "legacy_execution_compatibility.json",
            deployment_registry=deployment_registry,
        )
    )
    compatibility_registry.initialize_empty()

    if eligible:
        compatibility_registry.register(
            CustomerLegacyExecutionCompatibilityRecord(
                deployment_id=deployment.deployment_id,
                setup_activation_id="setup-activation-001",
                recovery_request_id=(
                    "setup-continuity-recovery:deployment-001"
                ),
            )
        )

    entitlement_registry = CustomerDeploymentEntitlementRegistry(
        tmp_path / "entitlements.json",
        deployment_registry=deployment_registry,
    )
    entitlement_registry.initialize_empty()

    if activate_entitlement:
        entitlement_registry.activate(
            deployment_id=deployment.deployment_id
        )

    entitlement_authorizer = CustomerDeploymentEntitlementAuthorizer(
        entitlement_registry=entitlement_registry,
    )

    binding_store = TrustedAgentAccountBindingStore(
        tmp_path / "bindings.json"
    )
    binding_store.initialize_empty()
    binding_store.bind(
        agent_id=deployment.agent_id,
        account_fingerprint="Broker-A:123456",
    )

    authorizer = CustomerLegacyDeploymentExecutionAuthorizer(
        deployment_registry=deployment_registry,
        compatibility_registry=compatibility_registry,
        entitlement_authorizer=entitlement_authorizer,
        account_binding_guard=TrustedAgentAccountBindingGuard(
            binding_store
        ),
    )

    return authorizer, entitlement_registry, deployment


def test_unknown_agent_fails_closed(tmp_path):
    authorizer, _, _ = _build_authorizer(tmp_path)

    with pytest.raises(
        RuntimeError,
        match="could not be resolved",
    ):
        authorizer.authorize(
            agent_id="trusted-agent-missing",
            account_fingerprint="Broker-A:123456",
        )


def test_account_mismatch_fails_closed(tmp_path):
    authorizer, _, _ = _build_authorizer(tmp_path)

    with pytest.raises(
        RuntimeError,
        match="does not match",
    ):
        authorizer.authorize(
            agent_id="trusted-agent-001",
            account_fingerprint="Broker-B:999999",
        )


def test_missing_entitlement_fails_closed(tmp_path):
    authorizer, _, _ = _build_authorizer(
        tmp_path,
        activate_entitlement=False,
    )

    with pytest.raises(
        RuntimeError,
        match="not entitled",
    ):
        authorizer.authorize(
            agent_id="trusted-agent-001",
            account_fingerprint="Broker-A:123456",
        )


def test_suspended_entitlement_fails_closed(tmp_path):
    authorizer, entitlement_registry, deployment = (
        _build_authorizer(tmp_path)
    )

    entitlement_registry.suspend(
        deployment_id=deployment.deployment_id
    )

    with pytest.raises(
        RuntimeError,
        match="not entitled",
    ):
        authorizer.authorize(
            agent_id="trusted-agent-001",
            account_fingerprint="Broker-A:123456",
        )



def test_missing_compatibility_eligibility_fails_closed(
    tmp_path,
):
    authorizer, _, _ = _build_authorizer(
        tmp_path,
        eligible=False,
    )

    with pytest.raises(
        RuntimeError,
        match="not eligible for legacy execution compatibility",
    ):
        authorizer.authorize(
            agent_id="trusted-agent-001",
            account_fingerprint="Broker-A:123456",
        )



def test_missing_eligibility_fails_before_account_binding_check(
    tmp_path,
):
    authorizer, _, _ = _build_authorizer(
        tmp_path,
        eligible=False,
    )

    with pytest.raises(
        RuntimeError,
        match="not eligible for legacy execution compatibility",
    ):
        authorizer.authorize(
            agent_id="trusted-agent-001",
            account_fingerprint="Broker-WRONG:999999",
        )


def test_missing_eligibility_fails_before_entitlement_check(
    tmp_path,
):
    authorizer, _, _ = _build_authorizer(
        tmp_path,
        eligible=False,
        activate_entitlement=False,
    )

    with pytest.raises(
        RuntimeError,
        match="not eligible for legacy execution compatibility",
    ):
        authorizer.authorize(
            agent_id="trusted-agent-001",
            account_fingerprint="Broker-A:123456",
        )


def test_constructor_requires_explicit_compatibility_registry_dependency():
    parameters = inspect.signature(
        CustomerLegacyDeploymentExecutionAuthorizer.__init__
    ).parameters

    assert list(parameters) == [
        "self",
        "deployment_registry",
        "compatibility_registry",
        "entitlement_authorizer",
        "account_binding_guard",
    ]
