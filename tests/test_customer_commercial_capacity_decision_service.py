from __future__ import annotations

import inspect
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.commercial.customer_commercial_billing_cycle_baseline_service import (
    CustomerCommercialBillingCycleBaselineRecord,
)
from backend.commercial.customer_commercial_capacity_decision_service import (
    CustomerCommercialCapacityDecisionStatus,
    CustomerCommercialCapacityDecisionService,
)
from backend.commercial.customer_commercial_deployment_binding import (
    CustomerCommercialDeploymentBinding,
)
from backend.commercial.customer_commercial_entitlement_registry import (
    CustomerCommercialEntitlement,
    CustomerCommercialEntitlementStatus,
)
from backend.commercial.customer_commercial_external_funding_observation_service import (
    CustomerCommercialExternalFundingObservationRecord,
)


def _entitlement(
    *,
    status: CustomerCommercialEntitlementStatus = (
        CustomerCommercialEntitlementStatus.ACTIVE
    ),
    customer_id: str = "customer-001",
    cap: int = 1000,
) -> CustomerCommercialEntitlement:
    return CustomerCommercialEntitlement(
        entitlement_id="commercial-entitlement-settlement-001",
        order_id="order-001",
        customer_id=customer_id,
        licensed_account_cap_usd=cap,
        standard_monthly_price_usd=50,
        status=status,
    )


def _binding(
    *,
    customer_id: str = "customer-001",
    entitlement_id: str = (
        "commercial-entitlement-settlement-001"
    ),
    account_fingerprint: str = "RoboForex-Pro:68353796",
) -> CustomerCommercialDeploymentBinding:
    return CustomerCommercialDeploymentBinding(
        commercial_entitlement_id=entitlement_id,
        customer_id=customer_id,
        deployment_id="deployment-001",
        agent_id="trusted-agent-001",
        account_fingerprint=account_fingerprint,
    )


def _baseline(
    *,
    customer_id: str = "customer-001",
    balance: Decimal = Decimal("1000"),
    cap: int = 1000,
) -> CustomerCommercialBillingCycleBaselineRecord:
    return CustomerCommercialBillingCycleBaselineRecord(
        cycle_id="cycle-001",
        customer_id=customer_id,
        cycle_started_at=datetime(
            2026,
            9,
            18,
            0,
            0,
            tzinfo=timezone.utc,
        ),
        authoritative_cycle_balance_usd=balance,
        licensed_account_cap_usd=cap,
        standard_monthly_price_usd=50,
    )


def _funding(
    *,
    ticket: int,
    kind: str,
    amount: Decimal,
    cycle_id: str = "cycle-001",
    account_fingerprint: str = "RoboForex-Pro:68353796",
) -> CustomerCommercialExternalFundingObservationRecord:
    return CustomerCommercialExternalFundingObservationRecord(
        cycle_id=cycle_id,
        account_fingerprint=account_fingerprint,
        deal_ticket=ticket,
        funding_kind=kind,
        amount=amount,
    )


def _decide(
    *,
    entitlement: CustomerCommercialEntitlement | None = None,
    binding: CustomerCommercialDeploymentBinding | None = None,
    baseline: CustomerCommercialBillingCycleBaselineRecord | None = None,
    funding: tuple[
        CustomerCommercialExternalFundingObservationRecord,
        ...,
    ] = (),
):
    service = CustomerCommercialCapacityDecisionService()

    return service.decide(
        entitlement=(
            entitlement
            if entitlement is not None
            else _entitlement()
        ),
        deployment_binding=(
            binding
            if binding is not None
            else _binding()
        ),
        billing_cycle_baseline=(
            baseline
            if baseline is not None
            else _baseline()
        ),
        external_funding_observations=funding,
    )


def test_service_is_pure_fact_decision_boundary() -> None:
    signature = inspect.signature(
        CustomerCommercialCapacityDecisionService.decide
    )

    assert list(signature.parameters) == [
        "self",
        "entitlement",
        "deployment_binding",
        "billing_cycle_baseline",
        "external_funding_observations",
    ]

    source = inspect.getsource(
        CustomerCommercialCapacityDecisionService
    )

    forbidden = (
        "Store",
        "store=",
        "payment",
        "setup_activation",
        "MT5",
        "open_position",
        "close_position",
        "current_balance_usd",
        "equity_usd",
    )

    for token in forbidden:
        assert token not in source


def test_no_external_funding_allows_new_exposure() -> None:
    decision = _decide()

    assert (
        decision.status
        is CustomerCommercialCapacityDecisionStatus.ALLOW_NEW_EXPOSURE
    )

    assert decision.commercial_capacity_high_water_usd == Decimal(
        "1000"
    )

    assert decision.operational_grace_limit_usd == Decimal(
        "1050.00"
    )


def test_exact_five_percent_grace_remains_allowed() -> None:
    decision = _decide(
        funding=(
            _funding(
                ticket=101,
                kind="external_deposit",
                amount=Decimal("50"),
            ),
        ),
    )

    assert (
        decision.status
        is CustomerCommercialCapacityDecisionStatus.ALLOW_NEW_EXPOSURE
    )

    assert decision.commercial_capacity_high_water_usd == Decimal(
        "1050"
    )


def test_one_cent_over_grace_requires_upgrade() -> None:
    decision = _decide(
        funding=(
            _funding(
                ticket=101,
                kind="external_deposit",
                amount=Decimal("50.01"),
            ),
        ),
    )

    assert (
        decision.status
        is CustomerCommercialCapacityDecisionStatus.UPGRADE_REQUIRED
    )

    assert decision.commercial_capacity_high_water_usd == Decimal(
        "1050.01"
    )


def test_multiple_external_deposits_accumulate() -> None:
    decision = _decide(
        funding=(
            _funding(
                ticket=101,
                kind="external_deposit",
                amount=Decimal("20"),
            ),
            _funding(
                ticket=102,
                kind="external_deposit",
                amount=Decimal("31"),
            ),
        ),
    )

    assert (
        decision.status
        is CustomerCommercialCapacityDecisionStatus.UPGRADE_REQUIRED
    )

    assert decision.commercial_capacity_high_water_usd == Decimal(
        "1051"
    )


def test_external_withdrawal_does_not_downgrade_high_water() -> None:
    decision = _decide(
        funding=(
            _funding(
                ticket=101,
                kind="external_deposit",
                amount=Decimal("100"),
            ),
            _funding(
                ticket=102,
                kind="external_withdrawal",
                amount=Decimal("-1000"),
            ),
        ),
    )

    assert (
        decision.status
        is CustomerCommercialCapacityDecisionStatus.UPGRADE_REQUIRED
    )

    assert decision.commercial_capacity_high_water_usd == Decimal(
        "1100"
    )

def test_trading_profit_cannot_be_supplied_to_decision() -> None:
    signature = inspect.signature(
        CustomerCommercialCapacityDecisionService.decide
    )

    assert "current_balance_usd" not in signature.parameters
    assert "equity_usd" not in signature.parameters
    assert "trading_profit_usd" not in signature.parameters


def test_suspended_entitlement_fails_closed() -> None:
    with pytest.raises(
        ValueError,
        match="ACTIVE commercial entitlement",
    ):
        _decide(
            entitlement=_entitlement(
                status=(
                    CustomerCommercialEntitlementStatus.SUSPENDED
                )
            )
        )


def test_binding_must_match_entitlement_identity() -> None:
    with pytest.raises(
        ValueError,
        match="entitlement identity",
    ):
        _decide(
            binding=_binding(
                entitlement_id="commercial-entitlement-other"
            )
        )


def test_binding_customer_must_match_entitlement_customer() -> None:
    with pytest.raises(
        ValueError,
        match="customer identity",
    ):
        _decide(
            binding=_binding(
                customer_id="customer-other"
            )
        )


def test_baseline_customer_must_match_entitlement_customer() -> None:
    with pytest.raises(
        ValueError,
        match="customer identity",
    ):
        _decide(
            baseline=_baseline(
                customer_id="customer-other"
            )
        )


def test_baseline_cap_must_match_purchased_entitlement_cap() -> None:
    with pytest.raises(
        ValueError,
        match="licensed account cap",
    ):
        _decide(
            baseline=_baseline(
                cap=2000
            )
        )


def test_funding_must_belong_to_same_cycle() -> None:
    with pytest.raises(
        ValueError,
        match="billing cycle",
    ):
        _decide(
            funding=(
                _funding(
                    ticket=101,
                    kind="external_deposit",
                    amount=Decimal("1"),
                    cycle_id="cycle-other",
                ),
            )
        )


def test_funding_must_belong_to_bound_account() -> None:
    with pytest.raises(
        ValueError,
        match="account fingerprint",
    ):
        _decide(
            funding=(
                _funding(
                    ticket=101,
                    kind="external_deposit",
                    amount=Decimal("1"),
                    account_fingerprint="OtherBroker:999",
                ),
            )
        )


def test_decision_is_order_independent_for_authoritative_funding() -> None:
    first = _funding(
        ticket=101,
        kind="external_deposit",
        amount=Decimal("25"),
    )
    second = _funding(
        ticket=102,
        kind="external_deposit",
        amount=Decimal("30"),
    )

    forward = _decide(
        funding=(
            first,
            second,
        )
    )

    reverse = _decide(
        funding=(
            second,
            first,
        )
    )

    assert forward == reverse

    assert (
        forward.status
        is CustomerCommercialCapacityDecisionStatus.UPGRADE_REQUIRED
    )


def test_decision_contains_only_auditable_commercial_facts() -> None:
    decision = _decide(
        funding=(
            _funding(
                ticket=101,
                kind="external_deposit",
                amount=Decimal("25"),
            ),
        ),
    )

    assert decision.commercial_entitlement_id == (
        "commercial-entitlement-settlement-001"
    )
    assert decision.deployment_id == "deployment-001"
    assert decision.cycle_id == "cycle-001"
    assert decision.licensed_account_cap_usd == Decimal("1000")
    assert decision.operational_grace_limit_usd == Decimal("1050.00")
    assert decision.commercial_capacity_high_water_usd == Decimal(
        "1025"
    )
