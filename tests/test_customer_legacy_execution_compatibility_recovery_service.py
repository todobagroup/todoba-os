import inspect

import pytest

from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlementRegistry,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_legacy_execution_compatibility_recovery_service import (
    CustomerLegacyExecutionCompatibilityRecoveryService,
)
from backend.commercial.customer_legacy_execution_compatibility_registry import (
    CustomerLegacyExecutionCompatibilityRegistry,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationRecord,
    CustomerSetupActivationStatus,
    CustomerSetupActivationStore,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


def _ready_stack(
    tmp_path,
    *,
    activate_entitlement: bool = True,
    bind_account: bool = True,
    recovery_owned_activation: bool = True,
    activation_customer_id: str = "customer-001",
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

    entitlement_registry = CustomerDeploymentEntitlementRegistry(
        tmp_path / "entitlements.json",
        deployment_registry=deployment_registry,
    )
    entitlement_registry.initialize_empty()

    if activate_entitlement:
        entitlement_registry.activate(
            deployment_id=deployment.deployment_id
        )

    account_binding_store = TrustedAgentAccountBindingStore(
        tmp_path / "bindings.json"
    )
    account_binding_store.initialize_empty()

    if bind_account:
        account_binding_store.bind(
            agent_id=deployment.agent_id,
            account_fingerprint="Broker-A:123456",
        )

    activation_store = CustomerSetupActivationStore(
        tmp_path / "setup-activations.json"
    )
    activation_store.initialize_empty()

    activation_request_id = (
        "setup-continuity-recovery:deployment-001"
        if recovery_owned_activation
        else "ordinary-setup-request-001"
    )

    activation_store.register(
        CustomerSetupActivationRecord(
            activation_request_id=activation_request_id,
            setup_activation_id="setup-activation-001",
            customer_id=activation_customer_id,
            status=CustomerSetupActivationStatus.ACTIVE,
            deployment_id=None,
        )
    )

    activation_store.bind(
        setup_activation_id="setup-activation-001",
        deployment_id=deployment.deployment_id,
    )

    compatibility_registry = (
        CustomerLegacyExecutionCompatibilityRegistry(
            tmp_path / "legacy-execution-compatibility.json",
            deployment_registry=deployment_registry,
        )
    )
    compatibility_registry.initialize_empty()

    service = CustomerLegacyExecutionCompatibilityRecoveryService(
        deployment_registry=deployment_registry,
        entitlement_registry=entitlement_registry,
        account_binding_store=account_binding_store,
        activation_store=activation_store,
        compatibility_registry=compatibility_registry,
    )

    return (
        service,
        compatibility_registry,
        deployment,
    )


def test_recovery_owned_deployment_is_enrolled(
    tmp_path,
) -> None:
    service, compatibility_registry, deployment = (
        _ready_stack(tmp_path)
    )

    result = service.recover(
        deployment_id=deployment.deployment_id
    )

    assert result.deployment_id == deployment.deployment_id
    assert result.setup_activation_id == "setup-activation-001"
    assert result.recovery_request_id == (
        "setup-continuity-recovery:deployment-001"
    )

    assert compatibility_registry.get(
        deployment_id=deployment.deployment_id
    ) == result


def test_non_recovery_setup_activation_fails_closed(
    tmp_path,
) -> None:
    service, compatibility_registry, deployment = (
        _ready_stack(
            tmp_path,
            recovery_owned_activation=False,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="recovery-owned",
    ):
        service.recover(
            deployment_id=deployment.deployment_id
        )

    assert compatibility_registry.size() == 0


def test_missing_deployment_entitlement_fails_closed(
    tmp_path,
) -> None:
    service, compatibility_registry, deployment = (
        _ready_stack(
            tmp_path,
            activate_entitlement=False,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="ACTIVE customer deployment entitlement",
    ):
        service.recover(
            deployment_id=deployment.deployment_id
        )

    assert compatibility_registry.size() == 0


def test_missing_trusted_agent_binding_fails_closed(
    tmp_path,
) -> None:
    service, compatibility_registry, deployment = (
        _ready_stack(
            tmp_path,
            bind_account=False,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Trusted Agent account binding",
    ):
        service.recover(
            deployment_id=deployment.deployment_id
        )

    assert compatibility_registry.size() == 0


def test_activation_customer_mismatch_fails_closed(
    tmp_path,
) -> None:
    service, compatibility_registry, deployment = (
        _ready_stack(
            tmp_path,
            activation_customer_id="customer-OTHER",
        )
    )

    with pytest.raises(
        RuntimeError,
        match="customer identity mismatch",
    ):
        service.recover(
            deployment_id=deployment.deployment_id
        )

    assert compatibility_registry.size() == 0


def test_unknown_deployment_fails_closed(
    tmp_path,
) -> None:
    service, compatibility_registry, _ = (
        _ready_stack(tmp_path)
    )

    with pytest.raises(
        RuntimeError,
        match="deployment does not exist",
    ):
        service.recover(
            deployment_id="deployment-missing"
        )

    assert compatibility_registry.size() == 0



def test_recovery_retry_is_idempotent(
    tmp_path,
) -> None:
    service, compatibility_registry, deployment = (
        _ready_stack(tmp_path)
    )

    first = service.recover(
        deployment_id=deployment.deployment_id
    )
    second = service.recover(
        deployment_id=deployment.deployment_id
    )

    assert second is first
    assert compatibility_registry.size() == 1


def test_recover_accepts_only_deployment_identity() -> None:
    parameters = inspect.signature(
        CustomerLegacyExecutionCompatibilityRecoveryService.recover
    ).parameters

    assert list(parameters) == [
        "self",
        "deployment_id",
    ]


def test_recover_does_not_accept_caller_supplied_authority() -> None:
    parameters = inspect.signature(
        CustomerLegacyExecutionCompatibilityRecoveryService.recover
    ).parameters

    for forbidden in (
        "customer_id",
        "agent_id",
        "account_fingerprint",
        "setup_activation_id",
        "recovery_request_id",
    ):
        assert forbidden not in parameters
