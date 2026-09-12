from pathlib import Path

import pytest

from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderService,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)
from backend.commercial.customer_payment_evidence_service import (
    CustomerPaymentEvidenceService,
    CustomerPaymentEvidenceStore,
    PaymentEvidenceSource,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentService,
    CustomerPaymentIntentStore,
    PaymentRail,
)
from backend.commercial.customer_payment_settlement_service import (
    PaymentVerificationAssertion,
)
from backend.commercial.customer_vnd_bank_reconciliation_service import (
    CustomerVndBankReconciliationService,
    CustomerVndBankReconciliationStore,
)
from backend.commercial.customer_vnd_bank_reconciliation_verification_adapter import (
    CustomerVndBankReconciliationVerificationAdapter,
)


def _build(tmp_path: Path):
    identity_registry = CustomerIdentityRegistry(
        tmp_path / "customer-identities.json"
    )
    identity_registry.initialize_empty()

    customer = identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001",
        )
    )

    order_store = CustomerCommercialOrderStore(
        tmp_path / "orders.json"
    )
    order_store.initialize_empty()

    order_service = CustomerCommercialOrderService(
        order_store=order_store,
        customer_identity_registry=identity_registry,
    )

    order = order_service.create(
        order_request_id="order-request-001",
        authorized_customer=customer,
        amount_minor=2500000,
        currency="VND",
    )

    intent_store = CustomerPaymentIntentStore(
        tmp_path / "intents.json"
    )
    intent_store.initialize_empty()

    intent_service = CustomerPaymentIntentService(
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    intent = intent_service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    evidence_store = CustomerPaymentEvidenceStore(
        tmp_path / "evidence.json"
    )
    evidence_store.initialize_empty()

    evidence_service = CustomerPaymentEvidenceService(
        payment_evidence_store=evidence_store,
        payment_intent_store=intent_store,
    )

    evidence = evidence_service.receive(
        evidence_request_id="evidence-request-001",
        authorized_payment_intent=intent,
        evidence_source=PaymentEvidenceSource.VND_BANK_TRANSFER,
        external_evidence_id="VCB-20260911-000001",
    )

    reconciliation_store = CustomerVndBankReconciliationStore(
        tmp_path / "reconciliations.json"
    )
    reconciliation_store.initialize_empty()

    reconciliation_service = CustomerVndBankReconciliationService(
        reconciliation_store=reconciliation_store,
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    reconciliation = reconciliation_service.confirm(
        reconciliation_request_id="reconcile-request-001",
        payment_intent_id=intent.payment_intent_id,
        bank_reference="VCB-20260911-000001",
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
    )

    adapter = CustomerVndBankReconciliationVerificationAdapter(
        reconciliation_store=reconciliation_store,
        payment_evidence_store=evidence_store,
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    return (
        adapter,
        reconciliation,
        evidence,
        intent,
        order,
    )


def test_build_assertion_from_authoritative_vnd_bank_chain(
    tmp_path,
):
    (
        adapter,
        reconciliation,
        evidence,
        intent,
        order,
    ) = _build(tmp_path)

    assertion = adapter.build_assertion(
        reconciliation_id=reconciliation.reconciliation_id,
    )

    assert isinstance(
        assertion,
        PaymentVerificationAssertion,
    )
    assert (
        assertion.verification_assertion_id
        == f"vnd-bank-verification-{reconciliation.reconciliation_id}"
    )
    assert assertion.payment_evidence_id == evidence.payment_evidence_id
    assert assertion.payment_intent_id == intent.payment_intent_id
    assert assertion.order_id == order.order_id
    assert assertion.customer_id == order.customer_id
    assert assertion.amount_minor == order.amount_minor
    assert assertion.currency == "VND"
    assert (
        assertion.evidence_source
        is PaymentEvidenceSource.VND_BANK_TRANSFER
    )
    assert (
        assertion.external_evidence_id
        == reconciliation.bank_reference
    )


def test_assertion_is_deterministic(tmp_path):
    (
        adapter,
        reconciliation,
        _,
        _,
        _,
    ) = _build(tmp_path)

    first = adapter.build_assertion(
        reconciliation_id=reconciliation.reconciliation_id,
    )
    second = adapter.build_assertion(
        reconciliation_id=reconciliation.reconciliation_id,
    )

    assert second == first


def test_missing_reconciliation_is_rejected(tmp_path):
    (
        adapter,
        _,
        _,
        _,
        _,
    ) = _build(tmp_path)

    with pytest.raises(ValueError):
        adapter.build_assertion(
            reconciliation_id="vnd-bank-reconciliation-missing",
        )


def test_missing_evidence_is_rejected(tmp_path):
    (
        adapter,
        reconciliation,
        evidence,
        _,
        _,
    ) = _build(tmp_path)

    object.__setattr__(
        evidence,
        "external_evidence_id",
        "VCB-FORGED",
    )

    with pytest.raises(ValueError):
        adapter.build_assertion(
            reconciliation_id=reconciliation.reconciliation_id,
        )


def test_reconciliation_and_intent_must_match(tmp_path):
    (
        adapter,
        reconciliation,
        _,
        _,
        _,
    ) = _build(tmp_path)

    object.__setattr__(
        reconciliation,
        "payment_intent_id",
        "payment-intent-forged",
    )

    with pytest.raises(ValueError):
        adapter.build_assertion(
            reconciliation_id=reconciliation.reconciliation_id,
        )


def test_reconciliation_amount_must_match_order(tmp_path):
    (
        adapter,
        reconciliation,
        _,
        _,
        _,
    ) = _build(tmp_path)

    object.__setattr__(
        reconciliation,
        "amount_minor",
        1,
    )

    with pytest.raises(ValueError):
        adapter.build_assertion(
            reconciliation_id=reconciliation.reconciliation_id,
        )


def test_adapter_exposes_no_settlement_or_activation_authority(
    tmp_path,
):
    (
        adapter,
        _,
        _,
        _,
        _,
    ) = _build(tmp_path)

    forbidden_methods = (
        "settle",
        "mark_paid",
        "activate_setup",
        "activate_entitlement",
        "receive",
        "confirm",
    )

    for method_name in forbidden_methods:
        assert not hasattr(
            adapter,
            method_name,
        )

def test_reconciliation_must_remain_confirmed(
    tmp_path,
):
    (
        adapter,
        reconciliation,
        _,
        _,
        _,
    ) = _build(tmp_path)

    object.__setattr__(
        reconciliation,
        "status",
        "PENDING",
    )

    with pytest.raises(ValueError):
        adapter.build_assertion(
            reconciliation_id=reconciliation.reconciliation_id,
        )


def test_evidence_source_must_remain_vnd_bank_transfer(
    tmp_path,
):
    (
        adapter,
        reconciliation,
        evidence,
        _,
        _,
    ) = _build(tmp_path)

    object.__setattr__(
        evidence,
        "evidence_source",
        PaymentEvidenceSource.PAYPAL,
    )

    with pytest.raises(ValueError):
        adapter.build_assertion(
            reconciliation_id=reconciliation.reconciliation_id,
        )


def test_evidence_status_must_remain_received(
    tmp_path,
):
    (
        adapter,
        reconciliation,
        evidence,
        _,
        _,
    ) = _build(tmp_path)

    object.__setattr__(
        evidence,
        "status",
        "FORGED",
    )

    with pytest.raises(ValueError):
        adapter.build_assertion(
            reconciliation_id=reconciliation.reconciliation_id,
        )


def test_intent_rail_must_remain_vnd_bank_transfer(
    tmp_path,
):
    (
        adapter,
        reconciliation,
        _,
        intent,
        _,
    ) = _build(tmp_path)

    authoritative_intent = (
        adapter._payment_intent_store.get(
            payment_intent_id=intent.payment_intent_id
        )
    )
    assert authoritative_intent is not None

    object.__setattr__(
        authoritative_intent,
        "payment_rail",
        PaymentRail.PAYPAL,
    )

    with pytest.raises(ValueError):
        adapter.build_assertion(
            reconciliation_id=reconciliation.reconciliation_id,
        )


def test_intent_status_must_remain_pending(
    tmp_path,
):
    (
        adapter,
        reconciliation,
        _,
        intent,
        _,
    ) = _build(tmp_path)

    authoritative_intent = (
        adapter._payment_intent_store.get(
            payment_intent_id=intent.payment_intent_id
        )
    )
    assert authoritative_intent is not None

    object.__setattr__(
        authoritative_intent,
        "status",
        "FORGED",
    )

    with pytest.raises(ValueError):
        adapter.build_assertion(
            reconciliation_id=reconciliation.reconciliation_id,
        )


def test_order_customer_must_match_reconciliation(
    tmp_path,
):
    (
        adapter,
        reconciliation,
        _,
        _,
        order,
    ) = _build(tmp_path)

    authoritative_order = (
        adapter._order_store.get(
            order_id=order.order_id
        )
    )
    assert authoritative_order is not None

    object.__setattr__(
        authoritative_order,
        "customer_id",
        "customer-forged",
    )

    with pytest.raises(ValueError):
        adapter.build_assertion(
            reconciliation_id=reconciliation.reconciliation_id,
        )


def test_order_currency_must_match_reconciliation(
    tmp_path,
):
    (
        adapter,
        reconciliation,
        _,
        _,
        order,
    ) = _build(tmp_path)

    authoritative_order = (
        adapter._order_store.get(
            order_id=order.order_id
        )
    )
    assert authoritative_order is not None

    object.__setattr__(
        authoritative_order,
        "currency",
        "USD",
    )

    with pytest.raises(ValueError):
        adapter.build_assertion(
            reconciliation_id=reconciliation.reconciliation_id,
        )


def test_adapter_has_no_write_or_network_authority(
    tmp_path,
):
    (
        adapter,
        _,
        _,
        _,
        _,
    ) = _build(tmp_path)

    forbidden_methods = (
        "register",
        "save",
        "persist",
        "confirm",
        "receive",
        "settle",
        "activate_setup",
        "activate_entitlement",
        "post",
        "get",
    )

    for method_name in forbidden_methods:
        assert not hasattr(
            adapter,
            method_name,
        )
