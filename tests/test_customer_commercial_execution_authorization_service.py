from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.commercial.customer_commercial_billing_cycle_baseline_service import (
    CustomerCommercialBillingCycleBaselineRecord,
    CustomerCommercialBillingCycleBaselineStore,
)
from backend.commercial.customer_commercial_capacity_decision_provider import (
    CustomerCommercialCapacityDecisionProvider,
)
from backend.commercial.customer_commercial_capacity_decision_service import (
    CustomerCommercialCapacityDecisionService,
)
from backend.commercial.customer_commercial_current_billing_cycle_service import (
    CustomerCommercialCurrentBillingCycleService,
    CustomerCommercialCurrentBillingCycleStore,
)
from backend.commercial.customer_commercial_deployment_binding import (
    CustomerCommercialDeploymentBinding,
    CustomerCommercialDeploymentBindingStore,
)
from backend.commercial.customer_commercial_entitlement_registry import (
    CustomerCommercialEntitlement,
    CustomerCommercialEntitlementRegistry,
    CustomerCommercialEntitlementStatus,
)
from backend.commercial.customer_commercial_execution_authorization_service import (
    CustomerCommercialExecutionAuthorizationService,
)
from backend.commercial.customer_commercial_external_funding_observation_service import (
    CustomerCommercialExternalFundingObservationRecord,
    CustomerCommercialExternalFundingObservationStore,
)
from backend.commercial.customer_commercial_new_exposure_authorization_service import (
    CustomerCommercialNewExposureAuthorizationService,
)


def _ready_stack(tmp_path):
    entitlement_registry = CustomerCommercialEntitlementRegistry(
        tmp_path / "entitlements.json"
    )
    entitlement_registry.initialize_empty()

    binding_store = CustomerCommercialDeploymentBindingStore(
        tmp_path / "bindings.json"
    )
    binding_store.initialize_empty()

    baseline_store = CustomerCommercialBillingCycleBaselineStore(
        tmp_path / "baselines.json"
    )
    baseline_store.initialize_empty()

    current_store = CustomerCommercialCurrentBillingCycleStore(
        tmp_path / "current.json"
    )
    current_store.initialize_empty()

    funding_store = CustomerCommercialExternalFundingObservationStore(
        tmp_path / "funding.json"
    )
    funding_store.initialize_empty()

    current_service = CustomerCommercialCurrentBillingCycleService(
        store=current_store,
        billing_cycle_store=baseline_store,
    )

    provider = CustomerCommercialCapacityDecisionProvider(
        entitlement_registry=entitlement_registry,
        deployment_binding_store=binding_store,
        current_billing_cycle_service=current_service,
        external_funding_store=funding_store,
        capacity_decision_service=CustomerCommercialCapacityDecisionService(),
    )

    new_exposure_authorizer = (
        CustomerCommercialNewExposureAuthorizationService()
    )

    service = CustomerCommercialExecutionAuthorizationService(
        deployment_binding_store=binding_store,
        capacity_decision_provider=provider,
        new_exposure_authorizer=new_exposure_authorizer,
    )

    return (
        entitlement_registry,
        binding_store,
        baseline_store,
        current_service,
        funding_store,
        provider,
        service,
    )


def _seed_authorized_stack(tmp_path):
    (
        entitlement_registry,
        binding_store,
        baseline_store,
        current_service,
        funding_store,
        provider,
        service,
    ) = _ready_stack(tmp_path)

    entitlement_registry.register(
        CustomerCommercialEntitlement(
            entitlement_id="entitlement-001",
            order_id="order-001",
            customer_id="customer-001",
            licensed_account_cap_usd=1000,
            standard_monthly_price_usd=50,
            status=CustomerCommercialEntitlementStatus.ACTIVE,
        )
    )

    binding_store.register(
        CustomerCommercialDeploymentBinding(
            commercial_entitlement_id="entitlement-001",
            customer_id="customer-001",
            deployment_id="deployment-001",
            agent_id="agent-001",
            account_fingerprint="Broker-Pro:1001",
        )
    )

    baseline_store.save(
        CustomerCommercialBillingCycleBaselineRecord(
            cycle_id="cycle-001",
            customer_id="customer-001",
            cycle_started_at=datetime(
                2026,
                9,
                1,
                tzinfo=UTC,
            ),
            authoritative_cycle_balance_usd=Decimal("1000"),
            licensed_account_cap_usd=1000,
            standard_monthly_price_usd=50,
        )
    )

    current_service.set_current(
        customer_id="customer-001",
        cycle_id="cycle-001",
    )

    return service, funding_store


def test_existing_normal_commercial_authority_is_preserved(
    tmp_path,
) -> None:
    service, _ = _seed_authorized_stack(
        tmp_path
    )

    assert (
        service.authorize(
            agent_id="agent-001",
            account_fingerprint="Broker-Pro:1001",
        )
        is None
    )


def test_missing_commercial_binding_fails_closed(
    tmp_path,
) -> None:
    (
        _,
        _,
        _,
        _,
        _,
        _,
        service,
    ) = _ready_stack(
        tmp_path
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "commercial deployment binding "
            "could not be resolved"
        ),
    ):
        service.authorize(
            agent_id="agent-001",
            account_fingerprint="Broker-Pro:1001",
        )


def test_constructor_rejects_invalid_binding_store(
    tmp_path,
) -> None:
    (
        _,
        _,
        _,
        _,
        _,
        provider,
        service,
    ) = _ready_stack(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match="deployment_binding_store",
    ):
        CustomerCommercialExecutionAuthorizationService(
            deployment_binding_store=object(),
            capacity_decision_provider=provider,
            new_exposure_authorizer=(
                CustomerCommercialNewExposureAuthorizationService()
            ),
        )


def test_constructor_rejects_invalid_capacity_provider(
    tmp_path,
) -> None:
    (
        _,
        binding_store,
        _,
        _,
        _,
        provider,
        service,
    ) = _ready_stack(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match="capacity_decision_provider",
    ):
        CustomerCommercialExecutionAuthorizationService(
            deployment_binding_store=binding_store,
            capacity_decision_provider=object(),
            new_exposure_authorizer=(
                CustomerCommercialNewExposureAuthorizationService()
            ),
        )


def test_constructor_rejects_invalid_new_exposure_authorizer(
    tmp_path,
) -> None:
    (
        _,
        binding_store,
        _,
        _,
        _,
        provider,
        service,
    ) = _ready_stack(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match="new_exposure_authorizer",
    ):
        CustomerCommercialExecutionAuthorizationService(
            deployment_binding_store=binding_store,
            capacity_decision_provider=provider,
            new_exposure_authorizer=object(),
        )


def test_upgrade_required_remains_fail_closed(
    tmp_path,
) -> None:
    service, funding_store = _seed_authorized_stack(
        tmp_path
    )

    funding_store.save(
        CustomerCommercialExternalFundingObservationRecord(
            cycle_id="cycle-001",
            account_fingerprint="Broker-Pro:1001",
            deal_ticket=1001,
            funding_kind="external_deposit",
            amount=Decimal("100"),
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Commercial upgrade required",
    ):
        service.authorize(
            agent_id="agent-001",
            account_fingerprint="Broker-Pro:1001",
        )
