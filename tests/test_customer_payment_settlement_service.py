from dataclasses import replace
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
    CustomerPaymentSettlementService,
    CustomerPaymentSettlementStatus,
    CustomerPaymentSettlementStore,
    PaymentVerificationAssertion,
)


def _built_service(
    tmp_path: Path,
):
    identity_registry = CustomerIdentityRegistry(
        tmp_path / "customer_identities.json"
    )
    identity_registry.initialize_empty()

    order_store = CustomerCommercialOrderStore(
        tmp_path / "customer_commercial_orders.json"
    )
    order_store.initialize_empty()

    order_service = CustomerCommercialOrderService(
        order_store=order_store,
        customer_identity_registry=identity_registry,
    )

    intent_store = CustomerPaymentIntentStore(
        tmp_path / "customer_payment_intents.json"
    )
    intent_store.initialize_empty()

    intent_service = CustomerPaymentIntentService(
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    evidence_store = CustomerPaymentEvidenceStore(
        tmp_path / "customer_payment_evidence.json"
    )
    evidence_store.initialize_empty()

    evidence_service = CustomerPaymentEvidenceService(
        payment_evidence_store=evidence_store,
        payment_intent_store=intent_store,
    )

    settlement_store = CustomerPaymentSettlementStore(
        tmp_path / "customer_payment_settlements.json"
    )
    settlement_store.initialize_empty()

    settlement_service = CustomerPaymentSettlementService(
        settlement_store=settlement_store,
        payment_evidence_store=evidence_store,
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    return (
        settlement_service,
        settlement_store,
        evidence_service,
        intent_service,
        identity_registry,
        order_service,
    )


def _create_chain(
    *,
    evidence_service,
    intent_service,
    identity_registry,
    order_service,
    customer_id="customer-001",
    order_request_id="order-request-001",
    intent_request_id="intent-request-001",
    evidence_request_id="evidence-request-001",
    rail=PaymentRail.PAYPAL,
    external_evidence_id="EXT-001",
):
    customer = identity_registry.register(
        CustomerIdentity(
            customer_id=customer_id,
        )
    )

    order = order_service.create(
        order_request_id=order_request_id,
        authorized_customer=customer,
        amount_minor=1_000_000,
        currency="VND",
    )

    intent = intent_service.create(
        payment_intent_request_id=intent_request_id,
        authorized_order=order,
        payment_rail=rail,
    )

    source = (
        PaymentEvidenceSource.PAYPAL
        if rail is PaymentRail.PAYPAL
        else PaymentEvidenceSource.VND_BANK_TRANSFER
    )

    evidence = evidence_service.receive(
        evidence_request_id=evidence_request_id,
        authorized_payment_intent=intent,
        evidence_source=source,
        external_evidence_id=external_evidence_id,
    )

    assertion = PaymentVerificationAssertion(
        verification_assertion_id="verification-001",
        payment_evidence_id=evidence.payment_evidence_id,
        payment_intent_id=intent.payment_intent_id,
        order_id=order.order_id,
        customer_id=order.customer_id,
        amount_minor=order.amount_minor,
        currency=order.currency,
        evidence_source=source,
        external_evidence_id=external_evidence_id,
    )

    return order, intent, evidence, assertion


def test_exact_verified_chain_creates_settlement(
    tmp_path: Path,
):
    (
        service,
        store,
        evidence_service,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    order, intent, evidence, assertion = _create_chain(
        evidence_service=evidence_service,
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    result = service.settle(
        verification_assertion=assertion,
    )

    assert result.settlement_id.startswith(
        "payment-settlement-"
    )
    assert result.order_id == order.order_id
    assert result.customer_id == order.customer_id
    assert result.payment_intent_id == intent.payment_intent_id
    assert result.payment_evidence_id == evidence.payment_evidence_id
    assert result.amount_minor == 1_000_000
    assert result.currency == "VND"
    assert (
        result.status
        is CustomerPaymentSettlementStatus.SETTLED
    )

    assert store.size() == 1


def test_identical_assertion_retry_is_idempotent(
    tmp_path: Path,
):
    (
        service,
        store,
        evidence_service,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, _, _, assertion = _create_chain(
        evidence_service=evidence_service,
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    first = service.settle(
        verification_assertion=assertion,
    )
    second = service.settle(
        verification_assertion=assertion,
    )

    assert second == first
    assert store.size() == 1


@pytest.mark.parametrize(
    "field,value",
    (
        ("customer_id", "customer-forged"),
        ("amount_minor", 999_999),
        ("currency", "USD"),
        ("payment_intent_id", "payment-intent-forged"),
        ("payment_evidence_id", "payment-evidence-forged"),
        ("external_evidence_id", "EXT-FORGED"),
    ),
)
def test_assertion_mismatch_fails_closed(
    tmp_path: Path,
    field,
    value,
):
    (
        service,
        store,
        evidence_service,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, _, _, assertion = _create_chain(
        evidence_service=evidence_service,
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    forged = replace(
        assertion,
        **{
            field: value,
        },
    )

    with pytest.raises(
        ValueError,
        match="verification",
    ):
        service.settle(
            verification_assertion=forged,
        )

    assert store.size() == 0


def test_wrong_evidence_source_fails_closed(
    tmp_path: Path,
):
    (
        service,
        store,
        evidence_service,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, _, _, assertion = _create_chain(
        evidence_service=evidence_service,
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    forged = replace(
        assertion,
        evidence_source=(
            PaymentEvidenceSource.VND_BANK_TRANSFER
        ),
    )

    with pytest.raises(
        ValueError,
        match="verification",
    ):
        service.settle(
            verification_assertion=forged,
        )

    assert store.size() == 0


def test_same_assertion_id_cannot_change_facts(
    tmp_path: Path,
):
    (
        service,
        store,
        evidence_service,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, _, _, assertion = _create_chain(
        evidence_service=evidence_service,
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    service.settle(
        verification_assertion=assertion,
    )

    changed = replace(
        assertion,
        amount_minor=2_000_000,
    )

    with pytest.raises(
        ValueError,
        match="verification|authoritative|commercial",
    ):
        service.settle(
            verification_assertion=changed,
        )

    assert store.size() == 1


def test_same_evidence_cannot_create_second_settlement(
    tmp_path: Path,
):
    (
        service,
        store,
        evidence_service,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, _, _, assertion = _create_chain(
        evidence_service=evidence_service,
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    first = service.settle(
        verification_assertion=assertion,
    )

    replay = replace(
        assertion,
        verification_assertion_id="verification-002",
    )

    second = service.settle(
        verification_assertion=replay,
    )

    assert second.settlement_id == first.settlement_id
    assert store.size() == 1


def test_same_order_cannot_settle_through_second_intent(
    tmp_path: Path,
):
    (
        service,
        store,
        evidence_service,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    customer = identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001",
        )
    )

    order = order_service.create(
        order_request_id="order-request-001",
        authorized_customer=customer,
        amount_minor=1_000_000,
        currency="VND",
    )

    paypal_intent = intent_service.create(
        payment_intent_request_id="intent-paypal",
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    paypal_evidence = evidence_service.receive(
        evidence_request_id="evidence-paypal",
        authorized_payment_intent=paypal_intent,
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="PP-001",
    )

    first_assertion = PaymentVerificationAssertion(
        verification_assertion_id="verification-paypal",
        payment_evidence_id=paypal_evidence.payment_evidence_id,
        payment_intent_id=paypal_intent.payment_intent_id,
        order_id=order.order_id,
        customer_id=order.customer_id,
        amount_minor=order.amount_minor,
        currency=order.currency,
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="PP-001",
    )

    first = service.settle(
        verification_assertion=first_assertion,
    )

    bank_intent = intent_service.create(
        payment_intent_request_id="intent-bank",
        authorized_order=order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    bank_evidence = evidence_service.receive(
        evidence_request_id="evidence-bank",
        authorized_payment_intent=bank_intent,
        evidence_source=(
            PaymentEvidenceSource.VND_BANK_TRANSFER
        ),
        external_evidence_id="BANK-001",
    )

    second_assertion = PaymentVerificationAssertion(
        verification_assertion_id="verification-bank",
        payment_evidence_id=bank_evidence.payment_evidence_id,
        payment_intent_id=bank_intent.payment_intent_id,
        order_id=order.order_id,
        customer_id=order.customer_id,
        amount_minor=order.amount_minor,
        currency=order.currency,
        evidence_source=(
            PaymentEvidenceSource.VND_BANK_TRANSFER
        ),
        external_evidence_id="BANK-001",
    )

    second = service.settle(
        verification_assertion=second_assertion,
    )

    assert second.settlement_id == first.settlement_id
    assert store.size() == 1


@pytest.mark.parametrize(
    "bad_amount",
    (
        0,
        -1,
        True,
        10.5,
        "1000000",
    ),
)
def test_verification_assertion_rejects_invalid_amount(
    bad_amount,
):
    with pytest.raises(
        (TypeError, ValueError),
    ):
        PaymentVerificationAssertion(
            verification_assertion_id="verification-001",
            payment_evidence_id="payment-evidence-001",
            payment_intent_id="payment-intent-001",
            order_id="commercial-order-001",
            customer_id="customer-001",
            amount_minor=bad_amount,
            currency="VND",
            evidence_source=PaymentEvidenceSource.PAYPAL,
            external_evidence_id="EXT-001",
        )


def test_settlement_exposes_no_activation_authority(
    tmp_path: Path,
):
    (
        service,
        store,
        _,
        _,
        _,
        _,
    ) = _built_service(tmp_path)

    forbidden = (
        "activate_setup",
        "activate_entitlement",
        "issue_access_code",
        "provision",
    )

    for owner in (
        service,
        store,
    ):
        for name in forbidden:
            assert not hasattr(
                owner,
                name,
            )

def test_corrupt_payment_settlement_store_fails_closed(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_settlements.json"
    )

    storage_path.write_text(
        "{not-json",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="unreadable",
    ):
        CustomerPaymentSettlementStore(
            storage_path
        )


def test_payment_settlement_store_rejects_unknown_fields(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_settlements.json"
    )

    storage_path.write_text(
        """
{
  "version": 1,
  "records": [],
  "unexpected": true
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="invalid fields",
    ):
        CustomerPaymentSettlementStore(
            storage_path
        )


def test_payment_settlement_store_rejects_duplicate_settlement_id(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_settlements.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "verification_assertion_id": "verification-001",
      "settlement_id": "payment-settlement-001",
      "payment_evidence_id": "payment-evidence-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "customer_id": "customer-001",
      "amount_minor": 1000000,
      "currency": "VND",
      "status": "SETTLED"
    },
    {
      "verification_assertion_id": "verification-002",
      "settlement_id": "payment-settlement-001",
      "payment_evidence_id": "payment-evidence-002",
      "payment_intent_id": "payment-intent-002",
      "order_id": "commercial-order-002",
      "customer_id": "customer-002",
      "amount_minor": 1000000,
      "currency": "VND",
      "status": "SETTLED"
    }
  ],
  "version": 1
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate customer payment settlement ID",
    ):
        CustomerPaymentSettlementStore(
            storage_path
        )


def test_payment_settlement_store_rejects_duplicate_assertion(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_settlements.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "verification_assertion_id": "verification-001",
      "settlement_id": "payment-settlement-001",
      "payment_evidence_id": "payment-evidence-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "customer_id": "customer-001",
      "amount_minor": 1000000,
      "currency": "VND",
      "status": "SETTLED"
    },
    {
      "verification_assertion_id": "verification-001",
      "settlement_id": "payment-settlement-002",
      "payment_evidence_id": "payment-evidence-002",
      "payment_intent_id": "payment-intent-002",
      "order_id": "commercial-order-002",
      "customer_id": "customer-002",
      "amount_minor": 1000000,
      "currency": "VND",
      "status": "SETTLED"
    }
  ],
  "version": 1
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate payment verification assertion",
    ):
        CustomerPaymentSettlementStore(
            storage_path
        )


def test_payment_settlement_store_rejects_duplicate_evidence(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_settlements.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "verification_assertion_id": "verification-001",
      "settlement_id": "payment-settlement-001",
      "payment_evidence_id": "payment-evidence-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "customer_id": "customer-001",
      "amount_minor": 1000000,
      "currency": "VND",
      "status": "SETTLED"
    },
    {
      "verification_assertion_id": "verification-002",
      "settlement_id": "payment-settlement-002",
      "payment_evidence_id": "payment-evidence-001",
      "payment_intent_id": "payment-intent-002",
      "order_id": "commercial-order-002",
      "customer_id": "customer-002",
      "amount_minor": 1000000,
      "currency": "VND",
      "status": "SETTLED"
    }
  ],
  "version": 1
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate settlement payment evidence",
    ):
        CustomerPaymentSettlementStore(
            storage_path
        )


def test_payment_settlement_store_rejects_duplicate_order(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_settlements.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "verification_assertion_id": "verification-001",
      "settlement_id": "payment-settlement-001",
      "payment_evidence_id": "payment-evidence-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "customer_id": "customer-001",
      "amount_minor": 1000000,
      "currency": "VND",
      "status": "SETTLED"
    },
    {
      "verification_assertion_id": "verification-002",
      "settlement_id": "payment-settlement-002",
      "payment_evidence_id": "payment-evidence-002",
      "payment_intent_id": "payment-intent-002",
      "order_id": "commercial-order-001",
      "customer_id": "customer-001",
      "amount_minor": 1000000,
      "currency": "VND",
      "status": "SETTLED"
    }
  ],
  "version": 1
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate settlement commercial order",
    ):
        CustomerPaymentSettlementStore(
            storage_path
        )


@pytest.mark.parametrize(
    "bad_status",
    (
        "PENDING",
        "VERIFIED",
        "PAID",
        "",
    ),
)
def test_payment_settlement_store_rejects_non_settled_status(
    tmp_path: Path,
    bad_status: str,
):
    storage_path = (
        tmp_path / "customer_payment_settlements.json"
    )

    storage_path.write_text(
        (
            """
{
  "records": [
    {
      "verification_assertion_id": "verification-001",
      "settlement_id": "payment-settlement-001",
      "payment_evidence_id": "payment-evidence-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "customer_id": "customer-001",
      "amount_minor": 1000000,
      "currency": "VND",
      "status": "__STATUS__"
    }
  ],
  "version": 1
}
""".replace(
                "__STATUS__",
                bad_status,
            ).strip()
            + "\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="invalid",
    ):
        CustomerPaymentSettlementStore(
            storage_path
        )


def test_payment_settlement_restore_preserves_all_indexes(
    tmp_path: Path,
):
    (
        service,
        _,
        evidence_service,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, _, evidence, assertion = _create_chain(
        evidence_service=evidence_service,
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    created = service.settle(
        verification_assertion=assertion,
    )

    restored = CustomerPaymentSettlementStore(
        tmp_path / "customer_payment_settlements.json"
    )

    assert restored.is_ready()

    by_id = restored.get(
        settlement_id=created.settlement_id,
    )

    by_assertion = (
        restored.get_by_verification_assertion_id(
            verification_assertion_id=(
                assertion.verification_assertion_id
            )
        )
    )

    by_evidence = restored.get_by_payment_evidence_id(
        payment_evidence_id=evidence.payment_evidence_id,
    )

    by_order = restored.get_by_order_id(
        order_id=created.order_id,
    )

    assert by_id == created
    assert by_assertion == created
    assert by_evidence == created
    assert by_order == created


def test_settlement_snapshot_contains_only_verified_commercial_truth(
    tmp_path: Path,
):
    (
        service,
        store,
        evidence_service,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, _, _, assertion = _create_chain(
        evidence_service=evidence_service,
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    result = service.settle(
        verification_assertion=assertion,
    )

    record = store.get(
        settlement_id=result.settlement_id,
    )

    assert record is not None

    assert set(record.__dict__) == {
        "verification_assertion_id",
        "settlement_id",
        "payment_evidence_id",
        "payment_intent_id",
        "order_id",
        "customer_id",
        "amount_minor",
        "currency",
        "status",
    }


def test_same_order_second_assertion_with_forged_amount_does_not_bypass(
    tmp_path: Path,
):
    (
        service,
        store,
        evidence_service,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, _, _, assertion = _create_chain(
        evidence_service=evidence_service,
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    service.settle(
        verification_assertion=assertion,
    )

    forged = replace(
        assertion,
        verification_assertion_id="verification-002",
        amount_minor=2_000_000,
    )

    with pytest.raises(
        ValueError,
        match="verification",
    ):
        service.settle(
            verification_assertion=forged,
        )

    assert store.size() == 1


def test_same_order_second_assertion_with_forged_customer_does_not_bypass(
    tmp_path: Path,
):
    (
        service,
        store,
        evidence_service,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, _, _, assertion = _create_chain(
        evidence_service=evidence_service,
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    service.settle(
        verification_assertion=assertion,
    )

    forged = replace(
        assertion,
        verification_assertion_id="verification-002",
        customer_id="customer-attacker",
    )

    with pytest.raises(
        ValueError,
        match="verification",
    ):
        service.settle(
            verification_assertion=forged,
        )

    assert store.size() == 1

def test_same_assertion_id_cannot_change_external_evidence_identity(
    tmp_path,
):
    (
        service,
        store,
        evidence_service,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    (
        _,
        _,
        _,
        assertion,
    ) = _create_chain(
        evidence_service=evidence_service,
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        external_evidence_id="PAYPAL-CAPTURE-001",
    )

    first = service.settle(
        verification_assertion=assertion,
    )

    forged = replace(
        assertion,
        external_evidence_id="PAYPAL-CAPTURE-FORGED",
    )

    with pytest.raises(
        ValueError,
        match="verification",
    ):
        service.settle(
            verification_assertion=forged,
        )

    assert store.size() == 1
    assert (
        store.get_by_verification_assertion_id(
            verification_assertion_id=(
                assertion.verification_assertion_id
            )
        )
        == first
    )


def test_same_assertion_id_cannot_change_evidence_source(
    tmp_path,
):
    (
        service,
        store,
        evidence_service,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    (
        _,
        _,
        _,
        assertion,
    ) = _create_chain(
        evidence_service=evidence_service,
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.PAYPAL,
        external_evidence_id="PAYPAL-CAPTURE-001",
    )

    first = service.settle(
        verification_assertion=assertion,
    )

    forged = replace(
        assertion,
        evidence_source=(
            PaymentEvidenceSource.VND_BANK_TRANSFER
        ),
    )

    with pytest.raises(
        ValueError,
        match="verification",
    ):
        service.settle(
            verification_assertion=forged,
        )

    assert store.size() == 1
    assert (
        store.get_by_verification_assertion_id(
            verification_assertion_id=(
                assertion.verification_assertion_id
            )
        )
        == first
    )
