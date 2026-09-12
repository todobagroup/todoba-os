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
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentService,
    CustomerPaymentIntentStore,
    PaymentRail,
)
from backend.commercial.customer_vnd_bank_reconciliation_service import (
    CustomerVndBankReconciliationService,
    CustomerVndBankReconciliationStatus,
    CustomerVndBankReconciliationStore,
)


def _build(tmp_path: Path):
    identity_registry = CustomerIdentityRegistry(
        tmp_path / "customer-identities.json"
    )
    identity_registry.initialize_empty()

    identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001",
        )
    )
    identity_registry.register(
        CustomerIdentity(
            customer_id="customer-002",
        )
    )

    order_store = CustomerCommercialOrderStore(
        storage_path=tmp_path / "orders.json"
    )
    order_store.initialize_empty()

    order_service = CustomerCommercialOrderService(
        order_store=order_store,
        customer_identity_registry=identity_registry,
    )

    intent_store = CustomerPaymentIntentStore(
        storage_path=tmp_path / "intents.json"
    )
    intent_store.initialize_empty()

    intent_service = CustomerPaymentIntentService(
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    reconciliation_store = CustomerVndBankReconciliationStore(
        storage_path=tmp_path / "bank-reconciliations.json"
    )
    reconciliation_store.initialize_empty()

    reconciliation_service = CustomerVndBankReconciliationService(
        reconciliation_store=reconciliation_store,
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    return (
        order_service,
        intent_service,
        reconciliation_service,
        reconciliation_store,
    )


def _create_order_and_intent(
    *,
    order_service,
    intent_service,
):
    order = order_service.create(
        order_request_id="order-request-001",
        authorized_customer=CustomerIdentity(
            customer_id="customer-001",
        ),
        amount_minor=2500000,
        currency="VND",
    )

    intent = intent_service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    return order, intent


def test_confirm_bank_reconciliation_binds_authoritative_chain(
    tmp_path,
):
    (
        order_service,
        intent_service,
        service,
        _,
    ) = _build(tmp_path)

    order, intent = _create_order_and_intent(
        order_service=order_service,
        intent_service=intent_service,
    )

    result = service.confirm(
        reconciliation_request_id="reconcile-request-001",
        payment_intent_id=intent.payment_intent_id,
        bank_reference="VCB-20260911-000001",
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
    )

    assert result.reconciliation_id.startswith(
        "vnd-bank-reconciliation-"
    )
    assert result.payment_intent_id == intent.payment_intent_id
    assert result.order_id == order.order_id
    assert result.customer_id == order.customer_id
    assert result.bank_reference == "VCB-20260911-000001"
    assert result.amount_minor == 2500000
    assert result.currency == "VND"
    assert result.operator_id == "operator-founder"
    assert (
        result.status
        is CustomerVndBankReconciliationStatus.CONFIRMED
    )


def test_same_request_is_idempotent(tmp_path):
    (
        order_service,
        intent_service,
        service,
        store,
    ) = _build(tmp_path)

    _, intent = _create_order_and_intent(
        order_service=order_service,
        intent_service=intent_service,
    )

    first = service.confirm(
        reconciliation_request_id="reconcile-request-001",
        payment_intent_id=intent.payment_intent_id,
        bank_reference="VCB-20260911-000001",
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
    )

    second = service.confirm(
        reconciliation_request_id="reconcile-request-001",
        payment_intent_id=intent.payment_intent_id,
        bank_reference="VCB-20260911-000001",
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
    )

    assert second == first
    assert store.size() == 1


def test_same_request_cannot_change_facts(tmp_path):
    (
        order_service,
        intent_service,
        service,
        _,
    ) = _build(tmp_path)

    _, intent = _create_order_and_intent(
        order_service=order_service,
        intent_service=intent_service,
    )

    service.confirm(
        reconciliation_request_id="reconcile-request-001",
        payment_intent_id=intent.payment_intent_id,
        bank_reference="VCB-20260911-000001",
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
    )

    with pytest.raises(ValueError):
        service.confirm(
            reconciliation_request_id="reconcile-request-001",
            payment_intent_id=intent.payment_intent_id,
            bank_reference="VCB-20260911-FORGED",
            amount_minor=2500000,
            currency="VND",
            operator_id="operator-founder",
        )


def test_bank_reference_cannot_be_replayed(
    tmp_path,
):
    (
        order_service,
        intent_service,
        service,
        _,
    ) = _build(tmp_path)

    _, first_intent = _create_order_and_intent(
        order_service=order_service,
        intent_service=intent_service,
    )

    second_order = order_service.create(
        order_request_id="order-request-002",
        authorized_customer=CustomerIdentity(
            customer_id="customer-002",
        ),
        amount_minor=2500000,
        currency="VND",
    )

    second_intent = intent_service.create(
        payment_intent_request_id="intent-request-002",
        authorized_order=second_order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    service.confirm(
        reconciliation_request_id="reconcile-request-001",
        payment_intent_id=first_intent.payment_intent_id,
        bank_reference="VCB-20260911-000001",
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
    )

    with pytest.raises(ValueError):
        service.confirm(
            reconciliation_request_id="reconcile-request-002",
            payment_intent_id=second_intent.payment_intent_id,
            bank_reference="VCB-20260911-000001",
            amount_minor=2500000,
            currency="VND",
            operator_id="operator-founder",
        )


def test_paypal_intent_is_rejected(tmp_path):
    (
        order_service,
        intent_service,
        service,
        _,
    ) = _build(tmp_path)

    order = order_service.create(
        order_request_id="order-request-001",
        authorized_customer=CustomerIdentity(
            customer_id="customer-001",
        ),
        amount_minor=2500000,
        currency="VND",
    )

    intent = intent_service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    with pytest.raises(ValueError):
        service.confirm(
            reconciliation_request_id="reconcile-request-001",
            payment_intent_id=intent.payment_intent_id,
            bank_reference="VCB-20260911-000001",
            amount_minor=2500000,
            currency="VND",
            operator_id="operator-founder",
        )


def test_amount_mismatch_is_rejected(tmp_path):
    (
        order_service,
        intent_service,
        service,
        _,
    ) = _build(tmp_path)

    _, intent = _create_order_and_intent(
        order_service=order_service,
        intent_service=intent_service,
    )

    with pytest.raises(ValueError):
        service.confirm(
            reconciliation_request_id="reconcile-request-001",
            payment_intent_id=intent.payment_intent_id,
            bank_reference="VCB-20260911-000001",
            amount_minor=1,
            currency="VND",
            operator_id="operator-founder",
        )


def test_non_vnd_currency_is_rejected(tmp_path):
    (
        order_service,
        intent_service,
        service,
        _,
    ) = _build(tmp_path)

    _, intent = _create_order_and_intent(
        order_service=order_service,
        intent_service=intent_service,
    )

    with pytest.raises(ValueError):
        service.confirm(
            reconciliation_request_id="reconcile-request-001",
            payment_intent_id=intent.payment_intent_id,
            bank_reference="VCB-20260911-000001",
            amount_minor=2500000,
            currency="USD",
            operator_id="operator-founder",
        )


def test_payment_intent_cannot_bind_second_bank_reference(
    tmp_path,
):
    (
        order_service,
        intent_service,
        service,
        store,
    ) = _build(tmp_path)

    _, intent = _create_order_and_intent(
        order_service=order_service,
        intent_service=intent_service,
    )

    first = service.confirm(
        reconciliation_request_id="reconcile-request-001",
        payment_intent_id=intent.payment_intent_id,
        bank_reference="VCB-20260911-000001",
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
    )

    with pytest.raises(ValueError):
        service.confirm(
            reconciliation_request_id="reconcile-request-002",
            payment_intent_id=intent.payment_intent_id,
            bank_reference="VCB-20260911-000002",
            amount_minor=2500000,
            currency="VND",
            operator_id="operator-founder",
        )

    assert store.size() == 1
    assert (
        store.get(
            reconciliation_id=first.reconciliation_id
        )
        == first
    )


def test_durable_reconciliation_restores_exact_truth(
    tmp_path,
):
    (
        order_service,
        intent_service,
        service,
        _,
    ) = _build(tmp_path)

    order, intent = _create_order_and_intent(
        order_service=order_service,
        intent_service=intent_service,
    )

    created = service.confirm(
        reconciliation_request_id="reconcile-request-001",
        payment_intent_id=intent.payment_intent_id,
        bank_reference="VCB-20260911-000001",
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
    )

    restored = CustomerVndBankReconciliationStore(
        storage_path=tmp_path / "bank-reconciliations.json"
    )
    restored.open_existing()

    record = restored.get(
        reconciliation_id=created.reconciliation_id
    )

    assert record == created
    assert record.payment_intent_id == intent.payment_intent_id
    assert record.order_id == order.order_id
    assert record.customer_id == order.customer_id
    assert record.bank_reference == "VCB-20260911-000001"
    assert record.amount_minor == 2500000
    assert record.currency == "VND"
    assert record.operator_id == "operator-founder"
    assert (
        record.status
        is CustomerVndBankReconciliationStatus.CONFIRMED
    )


def test_restored_store_preserves_bank_reference_replay_guard(
    tmp_path,
):
    (
        order_service,
        intent_service,
        service,
        _,
    ) = _build(tmp_path)

    _, intent = _create_order_and_intent(
        order_service=order_service,
        intent_service=intent_service,
    )

    created = service.confirm(
        reconciliation_request_id="reconcile-request-001",
        payment_intent_id=intent.payment_intent_id,
        bank_reference="VCB-20260911-000001",
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
    )

    restored = CustomerVndBankReconciliationStore(
        storage_path=tmp_path / "bank-reconciliations.json"
    )
    restored.open_existing()

    assert (
        restored.get_by_bank_reference(
            bank_reference="VCB-20260911-000001"
        )
        == created
    )

def test_restore_rejects_duplicate_payment_intent_id(
    tmp_path,
):
    storage_path = (
        tmp_path / "bank-reconciliations.json"
    )

    storage_path.write_text(
        """
[
  {
    "amount_minor": 2500000,
    "bank_reference": "VCB-20260911-000001",
    "currency": "VND",
    "customer_id": "customer-001",
    "operator_id": "operator-founder",
    "order_id": "commercial-order-001",
    "payment_intent_id": "payment-intent-001",
    "reconciliation_id": "vnd-bank-reconciliation-001",
    "reconciliation_request_id": "reconcile-request-001",
    "status": "CONFIRMED"
  },
  {
    "amount_minor": 2500000,
    "bank_reference": "VCB-20260911-000002",
    "currency": "VND",
    "customer_id": "customer-001",
    "operator_id": "operator-founder",
    "order_id": "commercial-order-001",
    "payment_intent_id": "payment-intent-001",
    "reconciliation_id": "vnd-bank-reconciliation-002",
    "reconciliation_request_id": "reconcile-request-002",
    "status": "CONFIRMED"
  }
]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    store = CustomerVndBankReconciliationStore(
        storage_path=storage_path
    )

    with pytest.raises(
        RuntimeError,
        match="Duplicate payment_intent_id",
    ):
        store.open_existing()


def test_p6a_owner_exposes_no_downstream_payment_authority(
    tmp_path,
):
    (
        _,
        _,
        service,
        store,
    ) = _build(tmp_path)

    forbidden_methods = (
        "receive",
        "receive_evidence",
        "build_assertion",
        "verify_payment",
        "settle",
        "mark_paid",
        "activate_setup",
        "activate_entitlement",
    )

    for owner in (
        service,
        store,
    ):
        for method_name in forbidden_methods:
            assert not hasattr(
                owner,
                method_name,
            )


def test_same_bank_reference_retry_cannot_change_request_identity(
    tmp_path,
):
    (
        order_service,
        intent_service,
        service,
        store,
    ) = _build(tmp_path)

    _, intent = _create_order_and_intent(
        order_service=order_service,
        intent_service=intent_service,
    )

    service.confirm(
        reconciliation_request_id="reconcile-request-001",
        payment_intent_id=intent.payment_intent_id,
        bank_reference="VCB-20260911-000001",
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
    )

    with pytest.raises(ValueError):
        service.confirm(
            reconciliation_request_id="reconcile-request-002",
            payment_intent_id=intent.payment_intent_id,
            bank_reference="VCB-20260911-000001",
            amount_minor=2500000,
            currency="VND",
            operator_id="operator-founder",
        )

    assert store.size() == 1
