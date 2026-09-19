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
    CustomerCommercialCapacityDecisionStatus,
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
from backend.commercial.customer_commercial_external_funding_observation_service import (
    CustomerCommercialExternalFundingObservationRecord,
    CustomerCommercialExternalFundingObservationStore,
)


def _ready(tmp_path):
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

    return (
        entitlement_registry,
        binding_store,
        baseline_store,
        current_service,
        funding_store,
        provider,
    )


def _seed_authorities(tmp_path):
    (
        entitlement_registry,
        binding_store,
        baseline_store,
        current_service,
        funding_store,
        provider,
    ) = _ready(tmp_path)

    entitlement = CustomerCommercialEntitlement(
        entitlement_id="entitlement-001",
        order_id="order-001",
        customer_id="customer-001",
        licensed_account_cap_usd=1000,
        standard_monthly_price_usd=50,
        status=CustomerCommercialEntitlementStatus.ACTIVE,
    )

    entitlement_registry.register(entitlement)

    binding = CustomerCommercialDeploymentBinding(
        commercial_entitlement_id="entitlement-001",
        customer_id="customer-001",
        deployment_id="deployment-001",
        agent_id="agent-001",
        account_fingerprint="Broker-Pro:1001",
    )

    binding_store.register(binding)

    baseline = CustomerCommercialBillingCycleBaselineRecord(
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

    baseline_store.save(baseline)

    current_service.set_current(
        customer_id="customer-001",
        cycle_id="cycle-001",
    )

    return (
        entitlement_registry,
        binding_store,
        baseline_store,
        current_service,
        funding_store,
        provider,
    )


def test_provider_returns_fresh_allow_decision(tmp_path) -> None:
    (
        _,
        _,
        _,
        _,
        _,
        provider,
    ) = _seed_authorities(tmp_path)

    decision = provider.provide(
        deployment_id="deployment-001"
    )

    assert (
        decision.status
        is CustomerCommercialCapacityDecisionStatus.ALLOW_NEW_EXPOSURE
    )


def test_provider_reflects_new_external_funding_each_call(
    tmp_path,
) -> None:
    (
        _,
        _,
        _,
        _,
        funding_store,
        provider,
    ) = _seed_authorities(tmp_path)

    first = provider.provide(
        deployment_id="deployment-001"
    )

    assert (
        first.status
        is CustomerCommercialCapacityDecisionStatus.ALLOW_NEW_EXPOSURE
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

    second = provider.provide(
        deployment_id="deployment-001"
    )

    assert (
        second.status
        is CustomerCommercialCapacityDecisionStatus.UPGRADE_REQUIRED
    )


def test_provider_ignores_other_cycle_or_account_funding(
    tmp_path,
) -> None:
    (
        _,
        _,
        _,
        _,
        funding_store,
        provider,
    ) = _seed_authorities(tmp_path)

    funding_store.save(
        CustomerCommercialExternalFundingObservationRecord(
            cycle_id="cycle-OTHER",
            account_fingerprint="Broker-Pro:1001",
            deal_ticket=2001,
            funding_kind="external_deposit",
            amount=Decimal("10000"),
        )
    )

    funding_store.save(
        CustomerCommercialExternalFundingObservationRecord(
            cycle_id="cycle-001",
            account_fingerprint="Broker-Pro:OTHER",
            deal_ticket=2002,
            funding_kind="external_deposit",
            amount=Decimal("10000"),
        )
    )

    decision = provider.provide(
        deployment_id="deployment-001"
    )

    assert (
        decision.status
        is CustomerCommercialCapacityDecisionStatus.ALLOW_NEW_EXPOSURE
    )


def test_unknown_deployment_fails_closed(tmp_path) -> None:
    *_, provider = _ready(tmp_path)

    with pytest.raises(
        RuntimeError,
        match="deployment",
    ):
        provider.provide(
            deployment_id="missing-deployment"
        )


def test_missing_entitlement_fails_closed(tmp_path) -> None:
    (
        _,
        binding_store,
        _,
        _,
        _,
        provider,
    ) = _ready(tmp_path)

    binding_store.register(
        CustomerCommercialDeploymentBinding(
            commercial_entitlement_id="missing-entitlement",
            customer_id="customer-001",
            deployment_id="deployment-001",
            agent_id="agent-001",
            account_fingerprint="Broker-Pro:1001",
        )
    )

    with pytest.raises(
        RuntimeError,
        match="entitlement",
    ):
        provider.provide(
            deployment_id="deployment-001"
        )


def test_provider_accepts_only_deployment_identity() -> None:
    import inspect

    parameters = inspect.signature(
        CustomerCommercialCapacityDecisionProvider.provide
    ).parameters

    assert list(parameters) == [
        "self",
        "deployment_id",
    ]
