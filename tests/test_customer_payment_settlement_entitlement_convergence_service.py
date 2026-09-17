from __future__ import annotations

from pathlib import Path

import pytest

from backend.commercial.customer_commercial_entitlement_registry import (
    CustomerCommercialEntitlementRegistry,
    CustomerCommercialEntitlementStatus,
)
from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderRecord,
    CustomerCommercialOrderStatus,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_commercial_order_terms_binding import (
    CustomerCommercialOrderTermsBindingRecord,
    CustomerCommercialOrderTermsBindingStore,
)
from backend.commercial.customer_payment_settlement_entitlement_convergence_service import (
    CustomerPaymentSettlementEntitlementConvergenceService,
)
from backend.commercial.customer_payment_settlement_service import (
    CustomerPaymentSettlementRecord,
    CustomerPaymentSettlementStatus,
    CustomerPaymentSettlementStore,
)


SETTLEMENT_ID = "payment-settlement-001"
ORDER_ID = "commercial-order-001"
CUSTOMER_ID = "customer-001"


def _context(
    tmp_path: Path,
):
    settlement_store = CustomerPaymentSettlementStore(
        tmp_path / "settlements.json"
    )
    settlement_store.initialize_empty()

    order_store = CustomerCommercialOrderStore(
        tmp_path / "orders.json"
    )
    order_store.initialize_empty()

    terms_store = CustomerCommercialOrderTermsBindingStore(
        tmp_path / "order_terms.json"
    )
    terms_store.initialize_empty()

    entitlement_registry = CustomerCommercialEntitlementRegistry(
        tmp_path / "entitlements.json"
    )
    entitlement_registry.initialize_empty()

    order_store.register(
        CustomerCommercialOrderRecord(
            order_request_id="order-request-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=2_120_100,
            currency="VND",
            status=CustomerCommercialOrderStatus.PENDING,
        )
    )

    terms_store.register(
        CustomerCommercialOrderTermsBindingRecord(
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            licensed_account_cap_usd=2000,
            standard_monthly_price_usd=80,
        )
    )

    settlement_store.register(
        CustomerPaymentSettlementRecord(
            verification_assertion_id="verification-001",
            settlement_id=SETTLEMENT_ID,
            payment_evidence_id="evidence-001",
            payment_intent_id="intent-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=2_120_100,
            currency="VND",
            status=CustomerPaymentSettlementStatus.SETTLED,
        )
    )

    service = CustomerPaymentSettlementEntitlementConvergenceService(
        settlement_store=settlement_store,
        order_store=order_store,
        order_terms_store=terms_store,
        entitlement_registry=entitlement_registry,
    )

    return {
        "service": service,
        "settlement_store": settlement_store,
        "order_store": order_store,
        "terms_store": terms_store,
        "entitlement_registry": entitlement_registry,
    }


def test_settled_payment_converges_exact_purchased_entitlement(
    tmp_path: Path,
):
    context = _context(tmp_path)

    result = context["service"].converge(
        settlement_id=SETTLEMENT_ID
    )

    assert result.entitlement_id == (
        "commercial-entitlement-"
        + SETTLEMENT_ID
    )
    assert result.order_id == ORDER_ID
    assert result.customer_id == CUSTOMER_ID
    assert result.licensed_account_cap_usd == 2000
    assert result.standard_monthly_price_usd == 80
    assert (
        result.status
        is CustomerCommercialEntitlementStatus.ACTIVE
    )

    assert (
        context["entitlement_registry"].get_by_order_id(
            order_id=ORDER_ID
        )
        == result
    )


def test_retry_is_idempotent(
    tmp_path: Path,
):
    context = _context(tmp_path)

    first = context["service"].converge(
        settlement_id=SETTLEMENT_ID
    )
    second = context["service"].converge(
        settlement_id=SETTLEMENT_ID
    )

    assert second == first
    assert (
        context["entitlement_registry"].size()
        == 1
    )


def test_missing_settlement_fails_closed(
    tmp_path: Path,
):
    context = _context(tmp_path)

    with pytest.raises(
        ValueError,
        match="settlement",
    ):
        context["service"].converge(
            settlement_id="payment-settlement-missing"
        )


def test_non_settled_truth_fails_closed(
    tmp_path: Path,
):
    context = _context(tmp_path)

    settlement = (
        context["settlement_store"].get(
            settlement_id=SETTLEMENT_ID
        )
    )
    assert settlement is not None

    object.__setattr__(
        settlement,
        "status",
        object(),
    )

    with pytest.raises(
        ValueError,
        match="settled",
    ):
        context["service"].converge(
            settlement_id=SETTLEMENT_ID
        )

    assert (
        context["entitlement_registry"].size()
        == 0
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("customer_id", "customer-forged"),
        ("amount_minor", 1),
        ("currency", "USD"),
    ),
)
def test_settlement_must_match_authoritative_order(
    tmp_path: Path,
    field: str,
    value,
):
    context = _context(tmp_path)

    order = context["order_store"].get(
        order_id=ORDER_ID
    )
    assert order is not None

    object.__setattr__(
        order,
        field,
        value,
    )

    with pytest.raises(
        ValueError,
        match="order",
    ):
        context["service"].converge(
            settlement_id=SETTLEMENT_ID
        )

    assert (
        context["entitlement_registry"].size()
        == 0
    )


def test_missing_order_terms_fail_closed(
    tmp_path: Path,
):
    context = _context(tmp_path)

    context["terms_store"]._records.clear()

    with pytest.raises(
        ValueError,
        match="terms",
    ):
        context["service"].converge(
            settlement_id=SETTLEMENT_ID
        )

    assert (
        context["entitlement_registry"].size()
        == 0
    )


def test_order_terms_customer_must_match_settlement_customer(
    tmp_path: Path,
):
    context = _context(tmp_path)

    terms = context["terms_store"].get_by_order_id(
        order_id=ORDER_ID
    )
    assert terms is not None

    context["terms_store"]._records[
        ORDER_ID
    ] = CustomerCommercialOrderTermsBindingRecord(
        order_id=ORDER_ID,
        customer_id="customer-forged",
        licensed_account_cap_usd=2000,
        standard_monthly_price_usd=80,
    )

    with pytest.raises(
        ValueError,
        match="terms",
    ):
        context["service"].converge(
            settlement_id=SETTLEMENT_ID
        )

    assert (
        context["entitlement_registry"].size()
        == 0
    )


def test_convergence_uses_authoritative_order_terms_not_paid_amount(
    tmp_path: Path,
):
    context = _context(tmp_path)

    result = context["service"].converge(
        settlement_id=SETTLEMENT_ID
    )

    assert result.licensed_account_cap_usd == 2000
    assert result.standard_monthly_price_usd == 80


def test_service_surface_accepts_only_settlement_id():
    import inspect

    signature = inspect.signature(
        CustomerPaymentSettlementEntitlementConvergenceService.converge
    )

    assert tuple(
        signature.parameters
    ) == (
        "self",
        "settlement_id",
    )


def test_service_has_no_setup_deployment_or_runtime_authority():
    forbidden = {
        "activate_setup",
        "bind_deployment",
        "authorize_runtime",
        "issue_activation_code",
    }

    assert forbidden.isdisjoint(
        set(
            dir(
                CustomerPaymentSettlementEntitlementConvergenceService
            )
        )
    )
