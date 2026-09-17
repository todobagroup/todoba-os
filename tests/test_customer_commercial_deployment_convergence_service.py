from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from backend.commercial.customer_commercial_deployment_binding import (
    CustomerCommercialDeploymentBinding,
    CustomerCommercialDeploymentBindingStore,
)
from backend.commercial.customer_commercial_deployment_convergence_service import (
    CustomerCommercialDeploymentConvergenceService,
)
from backend.commercial.customer_commercial_entitlement_registry import (
    CustomerCommercialEntitlement,
    CustomerCommercialEntitlementRegistry,
    CustomerCommercialEntitlementStatus,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationRecord,
    CustomerSetupActivationStatus,
    CustomerSetupActivationStore,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


CUSTOMER_ID = "customer-001"
ENTITLEMENT_ID = "commercial-entitlement-001"
ORDER_ID = "order-001"
SETUP_ACTIVATION_ID = "setup-activation-001"
ACTIVATION_REQUEST_ID = "activation-request-001"
DEPLOYMENT_ID = "deployment-001"
AGENT_ID = "trusted-agent-001"
ACCOUNT_FINGERPRINT = "RoboForex-Pro:68353796"


def _ready_sources(
    tmp_path: Path,
):
    entitlement_registry = (
        CustomerCommercialEntitlementRegistry(
            tmp_path / "commercial_entitlements.json"
        )
    )
    entitlement_registry.initialize_empty()

    activation_store = CustomerSetupActivationStore(
        tmp_path / "setup_activations.json"
    )
    activation_store.initialize_empty()

    deployment_registry = CustomerDeploymentRegistry(
        tmp_path / "deployments.json"
    )
    deployment_registry.initialize_empty()

    account_binding_store = TrustedAgentAccountBindingStore(
        tmp_path / "account_bindings.json"
    )
    account_binding_store.initialize_empty()

    binding_store = CustomerCommercialDeploymentBindingStore(
        tmp_path / "commercial_deployment_bindings.json"
    )
    binding_store.initialize_empty()

    return (
        entitlement_registry,
        activation_store,
        deployment_registry,
        account_binding_store,
        binding_store,
    )


def _service(
    tmp_path: Path,
):
    sources = _ready_sources(
        tmp_path
    )

    service = CustomerCommercialDeploymentConvergenceService(
        entitlement_registry=sources[0],
        activation_store=sources[1],
        deployment_registry=sources[2],
        account_binding_store=sources[3],
        binding_store=sources[4],
    )

    return (
        service,
        *sources,
    )


def _register_entitlement(
    registry: CustomerCommercialEntitlementRegistry,
    *,
    customer_id: str = CUSTOMER_ID,
):
    return registry.register(
        CustomerCommercialEntitlement(
            entitlement_id=ENTITLEMENT_ID,
            order_id=ORDER_ID,
            customer_id=customer_id,
            licensed_account_cap_usd=1000,
            standard_monthly_price_usd=50,
            status=(
                CustomerCommercialEntitlementStatus.ACTIVE
            ),
        )
    )


def _register_activation(
    store: CustomerSetupActivationStore,
    *,
    customer_id: str = CUSTOMER_ID,
    bind: bool = True,
    deployment_id: str = DEPLOYMENT_ID,
):
    store.register(
        CustomerSetupActivationRecord(
            activation_request_id=ACTIVATION_REQUEST_ID,
            setup_activation_id=SETUP_ACTIVATION_ID,
            customer_id=customer_id,
            status=CustomerSetupActivationStatus.ACTIVE,
            deployment_id=None,
        )
    )

    if bind:
        return store.bind(
            setup_activation_id=SETUP_ACTIVATION_ID,
            deployment_id=deployment_id,
        )

    return store.get(
        setup_activation_id=SETUP_ACTIVATION_ID
    )


def _register_deployment(
    registry: CustomerDeploymentRegistry,
    *,
    customer_id: str = CUSTOMER_ID,
    deployment_id: str = DEPLOYMENT_ID,
    agent_id: str = AGENT_ID,
):
    return registry.register(
        CustomerDeployment(
            customer_id=customer_id,
            deployment_id=deployment_id,
            agent_id=agent_id,
        )
    )


def _register_account_binding(
    store: TrustedAgentAccountBindingStore,
    *,
    agent_id: str = AGENT_ID,
    account_fingerprint: str = ACCOUNT_FINGERPRINT,
):
    return store.bind(
        agent_id=agent_id,
        account_fingerprint=account_fingerprint,
    )


def _register_complete_authority_chain(
    *,
    entitlement_registry,
    activation_store,
    deployment_registry,
    account_binding_store,
):
    entitlement = _register_entitlement(
        entitlement_registry
    )

    activation = _register_activation(
        activation_store
    )

    deployment = _register_deployment(
        deployment_registry
    )

    account_fingerprint = _register_account_binding(
        account_binding_store
    )

    return (
        entitlement,
        activation,
        deployment,
        account_fingerprint,
    )


def test_converge_caller_surface_is_exact():
    signature = inspect.signature(
        CustomerCommercialDeploymentConvergenceService.converge
    )

    assert tuple(
        signature.parameters
    ) == (
        "self",
        "commercial_entitlement_id",
        "setup_activation_id",
    )

    assert (
        signature.parameters[
            "commercial_entitlement_id"
        ].kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert (
        signature.parameters[
            "setup_activation_id"
        ].kind
        is inspect.Parameter.KEYWORD_ONLY
    )


def test_converges_authoritative_chain_to_exact_binding(
    tmp_path: Path,
):
    (
        service,
        entitlement_registry,
        activation_store,
        deployment_registry,
        account_binding_store,
        binding_store,
    ) = _service(
        tmp_path
    )

    (
        entitlement,
        _activation,
        deployment,
        account_fingerprint,
    ) = _register_complete_authority_chain(
        entitlement_registry=entitlement_registry,
        activation_store=activation_store,
        deployment_registry=deployment_registry,
        account_binding_store=account_binding_store,
    )

    result = service.converge(
        commercial_entitlement_id=(
            entitlement.entitlement_id
        ),
        setup_activation_id=SETUP_ACTIVATION_ID,
    )

    assert result == CustomerCommercialDeploymentBinding(
        commercial_entitlement_id=(
            entitlement.entitlement_id
        ),
        customer_id=CUSTOMER_ID,
        deployment_id=deployment.deployment_id,
        agent_id=deployment.agent_id,
        account_fingerprint=account_fingerprint,
    )

    assert (
        binding_store.get_by_entitlement_id(
            commercial_entitlement_id=(
                entitlement.entitlement_id
            )
        )
        == result
    )


def test_identical_convergence_retry_is_idempotent(
    tmp_path: Path,
):
    (
        service,
        entitlement_registry,
        activation_store,
        deployment_registry,
        account_binding_store,
        binding_store,
    ) = _service(
        tmp_path
    )

    _register_complete_authority_chain(
        entitlement_registry=entitlement_registry,
        activation_store=activation_store,
        deployment_registry=deployment_registry,
        account_binding_store=account_binding_store,
    )

    first = service.converge(
        commercial_entitlement_id=ENTITLEMENT_ID,
        setup_activation_id=SETUP_ACTIVATION_ID,
    )

    second = service.converge(
        commercial_entitlement_id=ENTITLEMENT_ID,
        setup_activation_id=SETUP_ACTIVATION_ID,
    )

    assert second == first
    assert binding_store.size() == 1


def test_missing_commercial_entitlement_fails_closed(
    tmp_path: Path,
):
    service, *_ = _service(
        tmp_path
    )

    with pytest.raises(
        RuntimeError,
        match="commercial entitlement",
    ):
        service.converge(
            commercial_entitlement_id=ENTITLEMENT_ID,
            setup_activation_id=SETUP_ACTIVATION_ID,
        )


def test_suspended_commercial_entitlement_fails_closed(
    tmp_path: Path,
):
    (
        service,
        entitlement_registry,
        activation_store,
        deployment_registry,
        account_binding_store,
        binding_store,
    ) = _service(
        tmp_path
    )

    _register_complete_authority_chain(
        entitlement_registry=entitlement_registry,
        activation_store=activation_store,
        deployment_registry=deployment_registry,
        account_binding_store=account_binding_store,
    )

    entitlement_registry.suspend(
        entitlement_id=ENTITLEMENT_ID
    )

    with pytest.raises(
        RuntimeError,
        match="ACTIVE commercial entitlement",
    ):
        service.converge(
            commercial_entitlement_id=ENTITLEMENT_ID,
            setup_activation_id=SETUP_ACTIVATION_ID,
        )

    assert binding_store.size() == 0


def test_missing_setup_activation_fails_closed(
    tmp_path: Path,
):
    (
        service,
        entitlement_registry,
        _activation_store,
        _deployment_registry,
        _account_binding_store,
        binding_store,
    ) = _service(
        tmp_path
    )

    _register_entitlement(
        entitlement_registry
    )

    with pytest.raises(
        RuntimeError,
        match="setup activation",
    ):
        service.converge(
            commercial_entitlement_id=ENTITLEMENT_ID,
            setup_activation_id=SETUP_ACTIVATION_ID,
        )

    assert binding_store.size() == 0


def test_non_bound_setup_activation_fails_closed(
    tmp_path: Path,
):
    (
        service,
        entitlement_registry,
        activation_store,
        _deployment_registry,
        _account_binding_store,
        binding_store,
    ) = _service(
        tmp_path
    )

    _register_entitlement(
        entitlement_registry
    )

    _register_activation(
        activation_store,
        bind=False,
    )

    with pytest.raises(
        RuntimeError,
        match="BOUND setup activation",
    ):
        service.converge(
            commercial_entitlement_id=ENTITLEMENT_ID,
            setup_activation_id=SETUP_ACTIVATION_ID,
        )

    assert binding_store.size() == 0


def test_cross_customer_activation_fails_closed(
    tmp_path: Path,
):
    (
        service,
        entitlement_registry,
        activation_store,
        deployment_registry,
        account_binding_store,
        binding_store,
    ) = _service(
        tmp_path
    )

    _register_entitlement(
        entitlement_registry,
        customer_id="customer-001",
    )

    _register_activation(
        activation_store,
        customer_id="customer-002",
    )

    _register_deployment(
        deployment_registry,
        customer_id="customer-002",
    )

    _register_account_binding(
        account_binding_store
    )

    with pytest.raises(
        RuntimeError,
        match="customer",
    ):
        service.converge(
            commercial_entitlement_id=ENTITLEMENT_ID,
            setup_activation_id=SETUP_ACTIVATION_ID,
        )

    assert binding_store.size() == 0


def test_missing_authoritative_deployment_fails_closed(
    tmp_path: Path,
):
    (
        service,
        entitlement_registry,
        activation_store,
        _deployment_registry,
        _account_binding_store,
        binding_store,
    ) = _service(
        tmp_path
    )

    _register_entitlement(
        entitlement_registry
    )

    _register_activation(
        activation_store
    )

    with pytest.raises(
        RuntimeError,
        match="customer deployment",
    ):
        service.converge(
            commercial_entitlement_id=ENTITLEMENT_ID,
            setup_activation_id=SETUP_ACTIVATION_ID,
        )

    assert binding_store.size() == 0


def test_cross_customer_deployment_fails_closed(
    tmp_path: Path,
):
    (
        service,
        entitlement_registry,
        activation_store,
        deployment_registry,
        _account_binding_store,
        binding_store,
    ) = _service(
        tmp_path
    )

    _register_entitlement(
        entitlement_registry
    )

    _register_activation(
        activation_store
    )

    _register_deployment(
        deployment_registry,
        customer_id="customer-other",
    )

    with pytest.raises(
        RuntimeError,
        match="customer",
    ):
        service.converge(
            commercial_entitlement_id=ENTITLEMENT_ID,
            setup_activation_id=SETUP_ACTIVATION_ID,
        )

    assert binding_store.size() == 0


def test_missing_authoritative_account_binding_fails_closed(
    tmp_path: Path,
):
    (
        service,
        entitlement_registry,
        activation_store,
        deployment_registry,
        _account_binding_store,
        binding_store,
    ) = _service(
        tmp_path
    )

    _register_entitlement(
        entitlement_registry
    )

    _register_activation(
        activation_store
    )

    _register_deployment(
        deployment_registry
    )

    with pytest.raises(
        RuntimeError,
        match="account binding",
    ):
        service.converge(
            commercial_entitlement_id=ENTITLEMENT_ID,
            setup_activation_id=SETUP_ACTIVATION_ID,
        )

    assert binding_store.size() == 0


def test_existing_binding_conflict_fails_closed(
    tmp_path: Path,
):
    (
        service,
        entitlement_registry,
        activation_store,
        deployment_registry,
        account_binding_store,
        binding_store,
    ) = _service(
        tmp_path
    )

    _register_complete_authority_chain(
        entitlement_registry=entitlement_registry,
        activation_store=activation_store,
        deployment_registry=deployment_registry,
        account_binding_store=account_binding_store,
    )

    binding_store.register(
        CustomerCommercialDeploymentBinding(
            commercial_entitlement_id=ENTITLEMENT_ID,
            customer_id=CUSTOMER_ID,
            deployment_id="deployment-other",
            agent_id="trusted-agent-other",
            account_fingerprint="Other-Broker:999999",
        )
    )

    with pytest.raises(
        ValueError,
        match="entitlement",
    ):
        service.converge(
            commercial_entitlement_id=ENTITLEMENT_ID,
            setup_activation_id=SETUP_ACTIVATION_ID,
        )

    assert binding_store.size() == 1


def test_service_has_no_mutating_or_network_authority():
    forbidden = {
        "settle",
        "activate",
        "suspend",
        "reactivate",
        "bind",
        "authorize",
        "urlopen",
        "fetch",
    }

    assert forbidden.isdisjoint(
        set(
            dir(
                CustomerCommercialDeploymentConvergenceService
            )
        )
    )
