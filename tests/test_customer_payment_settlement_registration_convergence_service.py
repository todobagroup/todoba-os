import inspect
from pathlib import Path

import pytest

from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderRecord,
    CustomerCommercialOrderStatus,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)
from backend.commercial.customer_payment_settlement_registration_convergence_service import (
    CustomerPaymentSettlementRegistrationConvergenceService,
)
from backend.commercial.customer_payment_settlement_service import (
    CustomerPaymentSettlementRecord,
    CustomerPaymentSettlementStatus,
    CustomerPaymentSettlementStore,
)
from backend.commercial.customer_registration_service import (
    CustomerRegistrationRecord,
    CustomerRegistrationStore,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationRecord,
    CustomerSetupActivationStatus,
    CustomerSetupActivationStore,
)


SETTLEMENT_ID = "payment-settlement-test-001"
ORDER_ID = "commercial-order-test-001"
CUSTOMER_ID = "customer-test-001"
AMOUNT_MINOR = 10_000
CURRENCY = "VND"

ACTIVATION_REQUEST_ID = (
    f"payment-settlement-activation-{SETTLEMENT_ID}"
)

REGISTRATION_REQUEST_ID = (
    f"payment-settlement-registration-{SETTLEMENT_ID}"
)


def _build_context(tmp_path: Path):
    settlement_store = CustomerPaymentSettlementStore(
        tmp_path / "customer_payment_settlements.json"
    )
    settlement_store.initialize_empty()

    order_store = CustomerCommercialOrderStore(
        tmp_path / "customer_commercial_orders.json"
    )
    order_store.initialize_empty()

    identity_registry = CustomerIdentityRegistry(
        tmp_path / "customer_identities.json"
    )
    identity_registry.initialize_empty()

    activation_store = CustomerSetupActivationStore(
        tmp_path / "customer_setup_activations.json"
    )
    activation_store.initialize_empty()

    registration_store = CustomerRegistrationStore(
        tmp_path / "customer_registrations.json"
    )
    registration_store.initialize_empty()

    service = (
        CustomerPaymentSettlementRegistrationConvergenceService(
            settlement_store=settlement_store,
            order_store=order_store,
            customer_identity_registry=identity_registry,
            setup_activation_store=activation_store,
            registration_store=registration_store,
        )
    )

    return {
        "service": service,
        "settlement_store": settlement_store,
        "order_store": order_store,
        "identity_registry": identity_registry,
        "activation_store": activation_store,
        "registration_store": registration_store,
    }


def _register_authoritative_chain(context) -> None:
    context["identity_registry"].register(
        CustomerIdentity(
            customer_id=CUSTOMER_ID,
        )
    )

    context["order_store"].register(
        CustomerCommercialOrderRecord(
            order_request_id="order-request-test-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerCommercialOrderStatus.PENDING,
        )
    )

    context["settlement_store"].register(
        CustomerPaymentSettlementRecord(
            verification_assertion_id=(
                "verification-assertion-test-001"
            ),
            settlement_id=SETTLEMENT_ID,
            payment_evidence_id="payment-evidence-test-001",
            payment_intent_id="payment-intent-test-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerPaymentSettlementStatus.SETTLED,
        )
    )

    context["activation_store"].register(
        CustomerSetupActivationRecord(
            activation_request_id=ACTIVATION_REQUEST_ID,
            setup_activation_id="setup-activation-test-001",
            customer_id=CUSTOMER_ID,
            status=CustomerSetupActivationStatus.ACTIVE,
        )
    )


def test_authority_surface_accepts_settlement_id_only():
    parameters = inspect.signature(
        CustomerPaymentSettlementRegistrationConvergenceService
        .converge
    ).parameters

    assert tuple(parameters) == (
        "self",
        "settlement_id",
    )

    assert "customer_id" not in parameters


def test_settled_authoritative_lineage_creates_registration(
    tmp_path: Path,
):
    context = _build_context(tmp_path)
    _register_authoritative_chain(context)

    result = context["service"].converge(
        settlement_id=SETTLEMENT_ID,
    )

    assert result == CustomerRegistrationRecord(
        registration_request_id=REGISTRATION_REQUEST_ID,
        customer_id=CUSTOMER_ID,
    )

    assert (
        context["registration_store"].get_by_customer_id(
            customer_id=CUSTOMER_ID,
        )
        == result
    )


def test_retry_is_deterministic_and_idempotent(
    tmp_path: Path,
):
    context = _build_context(tmp_path)
    _register_authoritative_chain(context)

    first = context["service"].converge(
        settlement_id=SETTLEMENT_ID,
    )
    second = context["service"].converge(
        settlement_id=SETTLEMENT_ID,
    )

    assert second == first
    assert (
        context["registration_store"].get_by_customer_id(
            customer_id=CUSTOMER_ID,
        )
        == first
    )


def test_existing_authoritative_registration_is_preserved(
    tmp_path: Path,
):
    context = _build_context(tmp_path)
    _register_authoritative_chain(context)

    existing = context["registration_store"].register(
        CustomerRegistrationRecord(
            registration_request_id=(
                "preexisting-registration-request"
            ),
            customer_id=CUSTOMER_ID,
        )
    )

    result = context["service"].converge(
        settlement_id=SETTLEMENT_ID,
    )

    assert result == existing


def test_unknown_settlement_fails_closed_without_registration(
    tmp_path: Path,
):
    context = _build_context(tmp_path)

    with pytest.raises(
        ValueError,
        match="settlement",
    ):
        context["service"].converge(
            settlement_id="payment-settlement-missing",
        )

    assert context["registration_store"].all() == ()


def test_missing_identity_fails_closed(
    tmp_path: Path,
):
    context = _build_context(tmp_path)

    context["order_store"].register(
        CustomerCommercialOrderRecord(
            order_request_id="order-request-test-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerCommercialOrderStatus.PENDING,
        )
    )

    context["settlement_store"].register(
        CustomerPaymentSettlementRecord(
            verification_assertion_id=(
                "verification-assertion-test-001"
            ),
            settlement_id=SETTLEMENT_ID,
            payment_evidence_id="payment-evidence-test-001",
            payment_intent_id="payment-intent-test-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerPaymentSettlementStatus.SETTLED,
        )
    )

    context["activation_store"].register(
        CustomerSetupActivationRecord(
            activation_request_id=ACTIVATION_REQUEST_ID,
            setup_activation_id="setup-activation-test-001",
            customer_id=CUSTOMER_ID,
            status=CustomerSetupActivationStatus.ACTIVE,
        )
    )

    with pytest.raises(
        ValueError,
        match="identity",
    ):
        context["service"].converge(
            settlement_id=SETTLEMENT_ID,
        )

    assert context["registration_store"].all() == ()


def test_missing_payment_derived_activation_fails_closed(
    tmp_path: Path,
):
    context = _build_context(tmp_path)

    context["identity_registry"].register(
        CustomerIdentity(
            customer_id=CUSTOMER_ID,
        )
    )

    context["order_store"].register(
        CustomerCommercialOrderRecord(
            order_request_id="order-request-test-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerCommercialOrderStatus.PENDING,
        )
    )

    context["settlement_store"].register(
        CustomerPaymentSettlementRecord(
            verification_assertion_id=(
                "verification-assertion-test-001"
            ),
            settlement_id=SETTLEMENT_ID,
            payment_evidence_id="payment-evidence-test-001",
            payment_intent_id="payment-intent-test-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerPaymentSettlementStatus.SETTLED,
        )
    )

    with pytest.raises(
        ValueError,
        match="activation",
    ):
        context["service"].converge(
            settlement_id=SETTLEMENT_ID,
        )

    assert context["registration_store"].all() == ()


def test_order_lineage_mismatch_fails_closed(
    tmp_path: Path,
):
    context = _build_context(tmp_path)

    context["identity_registry"].register(
        CustomerIdentity(
            customer_id=CUSTOMER_ID,
        )
    )

    context["order_store"].register(
        CustomerCommercialOrderRecord(
            order_request_id="order-request-test-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=20_000,
            currency=CURRENCY,
            status=CustomerCommercialOrderStatus.PENDING,
        )
    )

    context["settlement_store"].register(
        CustomerPaymentSettlementRecord(
            verification_assertion_id=(
                "verification-assertion-test-001"
            ),
            settlement_id=SETTLEMENT_ID,
            payment_evidence_id="payment-evidence-test-001",
            payment_intent_id="payment-intent-test-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerPaymentSettlementStatus.SETTLED,
        )
    )

    context["activation_store"].register(
        CustomerSetupActivationRecord(
            activation_request_id=ACTIVATION_REQUEST_ID,
            setup_activation_id="setup-activation-test-001",
            customer_id=CUSTOMER_ID,
            status=CustomerSetupActivationStatus.ACTIVE,
        )
    )

    with pytest.raises(
        ValueError,
        match="order",
    ):
        context["service"].converge(
            settlement_id=SETTLEMENT_ID,
        )

    assert context["registration_store"].all() == ()


def test_activation_for_different_customer_fails_closed(
    tmp_path: Path,
):
    context = _build_context(tmp_path)

    context["identity_registry"].register(
        CustomerIdentity(
            customer_id=CUSTOMER_ID,
        )
    )

    context["order_store"].register(
        CustomerCommercialOrderRecord(
            order_request_id="order-request-test-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerCommercialOrderStatus.PENDING,
        )
    )

    context["settlement_store"].register(
        CustomerPaymentSettlementRecord(
            verification_assertion_id=(
                "verification-assertion-test-001"
            ),
            settlement_id=SETTLEMENT_ID,
            payment_evidence_id="payment-evidence-test-001",
            payment_intent_id="payment-intent-test-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerPaymentSettlementStatus.SETTLED,
        )
    )

    context["activation_store"].register(
        CustomerSetupActivationRecord(
            activation_request_id=ACTIVATION_REQUEST_ID,
            setup_activation_id="setup-activation-test-001",
            customer_id="customer-other",
            status=CustomerSetupActivationStatus.ACTIVE,
        )
    )

    with pytest.raises(
        ValueError,
        match="activation",
    ):
        context["service"].converge(
            settlement_id=SETTLEMENT_ID,
        )

    assert context["registration_store"].all() == ()


def test_suspended_payment_derived_activation_fails_closed(
    tmp_path: Path,
):
    context = _build_context(tmp_path)

    context["identity_registry"].register(
        CustomerIdentity(
            customer_id=CUSTOMER_ID,
        )
    )

    context["order_store"].register(
        CustomerCommercialOrderRecord(
            order_request_id="order-request-test-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerCommercialOrderStatus.PENDING,
        )
    )

    context["settlement_store"].register(
        CustomerPaymentSettlementRecord(
            verification_assertion_id=(
                "verification-assertion-test-001"
            ),
            settlement_id=SETTLEMENT_ID,
            payment_evidence_id="payment-evidence-test-001",
            payment_intent_id="payment-intent-test-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerPaymentSettlementStatus.SETTLED,
        )
    )

    active = context["activation_store"].register(
        CustomerSetupActivationRecord(
            activation_request_id=ACTIVATION_REQUEST_ID,
            setup_activation_id="setup-activation-test-001",
            customer_id=CUSTOMER_ID,
            status=CustomerSetupActivationStatus.ACTIVE,
        )
    )

    context["activation_store"].suspend(
        setup_activation_id=active.setup_activation_id,
    )

    with pytest.raises(
        ValueError,
        match="activation",
    ):
        context["service"].converge(
            settlement_id=SETTLEMENT_ID,
        )

    assert context["registration_store"].all() == ()


def test_bound_payment_derived_activation_fails_closed(
    tmp_path: Path,
):
    context = _build_context(tmp_path)

    context["identity_registry"].register(
        CustomerIdentity(
            customer_id=CUSTOMER_ID,
        )
    )

    context["order_store"].register(
        CustomerCommercialOrderRecord(
            order_request_id="order-request-test-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerCommercialOrderStatus.PENDING,
        )
    )

    context["settlement_store"].register(
        CustomerPaymentSettlementRecord(
            verification_assertion_id=(
                "verification-assertion-test-001"
            ),
            settlement_id=SETTLEMENT_ID,
            payment_evidence_id="payment-evidence-test-001",
            payment_intent_id="payment-intent-test-001",
            order_id=ORDER_ID,
            customer_id=CUSTOMER_ID,
            amount_minor=AMOUNT_MINOR,
            currency=CURRENCY,
            status=CustomerPaymentSettlementStatus.SETTLED,
        )
    )

    active = context["activation_store"].register(
        CustomerSetupActivationRecord(
            activation_request_id=ACTIVATION_REQUEST_ID,
            setup_activation_id="setup-activation-test-001",
            customer_id=CUSTOMER_ID,
            status=CustomerSetupActivationStatus.ACTIVE,
        )
    )

    context["activation_store"].bind(
        setup_activation_id=active.setup_activation_id,
        deployment_id="deployment-test-001",
    )

    with pytest.raises(
        ValueError,
        match="activation",
    ):
        context["service"].converge(
            settlement_id=SETTLEMENT_ID,
        )

    assert context["registration_store"].all() == ()


def test_deterministic_registration_request_collision_fails_closed(
    tmp_path: Path,
):
    context = _build_context(tmp_path)
    _register_authoritative_chain(context)

    context["registration_store"].register(
        CustomerRegistrationRecord(
            registration_request_id=REGISTRATION_REQUEST_ID,
            customer_id="customer-other",
        )
    )

    with pytest.raises(
        ValueError,
        match="registration",
    ):
        context["service"].converge(
            settlement_id=SETTLEMENT_ID,
        )

    assert (
        context["registration_store"].get_by_customer_id(
            customer_id=CUSTOMER_ID,
        )
        is None
    )


@pytest.mark.parametrize(
    "dependency_name",
    (
        "settlement_store",
        "order_store",
        "customer_identity_registry",
        "setup_activation_store",
        "registration_store",
    ),
)
def test_constructor_requires_ready_authoritative_sources(
    tmp_path: Path,
    dependency_name: str,
):
    settlement_store = CustomerPaymentSettlementStore(
        tmp_path / "settlements.json"
    )
    order_store = CustomerCommercialOrderStore(
        tmp_path / "orders.json"
    )
    identity_registry = CustomerIdentityRegistry(
        tmp_path / "identities.json"
    )
    activation_store = CustomerSetupActivationStore(
        tmp_path / "activations.json"
    )
    registration_store = CustomerRegistrationStore(
        tmp_path / "registrations.json"
    )

    dependencies = {
        "settlement_store": settlement_store,
        "order_store": order_store,
        "customer_identity_registry": identity_registry,
        "setup_activation_store": activation_store,
        "registration_store": registration_store,
    }

    for name, dependency in dependencies.items():
        if name != dependency_name:
            dependency.initialize_empty()

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        CustomerPaymentSettlementRegistrationConvergenceService(
            settlement_store=settlement_store,
            order_store=order_store,
            customer_identity_registry=identity_registry,
            setup_activation_store=activation_store,
            registration_store=registration_store,
        )
