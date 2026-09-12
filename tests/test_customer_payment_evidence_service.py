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
    CustomerPaymentEvidenceRecord,
    CustomerPaymentEvidenceService,
    CustomerPaymentEvidenceStatus,
    CustomerPaymentEvidenceStore,
    PaymentEvidenceSource,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentService,
    CustomerPaymentIntentStore,
    PaymentRail,
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

    return (
        evidence_service,
        evidence_store,
        intent_service,
        identity_registry,
        order_service,
    )


def _create_intent(
    *,
    intent_service,
    identity_registry,
    order_service,
    rail: PaymentRail,
    customer_id: str = "customer-001",
    order_request_id: str = "order-request-001",
    intent_request_id: str = "intent-request-001",
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

    return intent_service.create(
        payment_intent_request_id=intent_request_id,
        authorized_order=order,
        payment_rail=rail,
    )


def test_receive_paypal_evidence_for_authoritative_intent(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.PAYPAL,
    )

    result = service.receive(
        evidence_request_id="evidence-request-001",
        authorized_payment_intent=intent,
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="WH-9A001",
    )

    assert result.payment_evidence_id.startswith(
        "payment-evidence-"
    )
    assert (
        result.evidence_request_id
        == "evidence-request-001"
    )
    assert (
        result.payment_intent_id
        == intent.payment_intent_id
    )
    assert (
        result.evidence_source
        is PaymentEvidenceSource.PAYPAL
    )
    assert result.external_evidence_id == "WH-9A001"
    assert (
        result.status
        is CustomerPaymentEvidenceStatus.RECEIVED
    )

    stored = store.get(
        payment_evidence_id=result.payment_evidence_id,
    )

    assert stored is not None
    assert stored == result


def test_receive_bank_transfer_evidence(
    tmp_path: Path,
):
    (
        service,
        _,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.VND_BANK_TRANSFER,
    )

    result = service.receive(
        evidence_request_id="evidence-request-001",
        authorized_payment_intent=intent,
        evidence_source=(
            PaymentEvidenceSource.VND_BANK_TRANSFER
        ),
        external_evidence_id="BANK-TXN-001",
    )

    assert (
        result.evidence_source
        is PaymentEvidenceSource.VND_BANK_TRANSFER
    )


def test_identical_receive_retry_is_idempotent(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.PAYPAL,
    )

    first = service.receive(
        evidence_request_id="evidence-request-001",
        authorized_payment_intent=intent,
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="WH-001",
    )

    second = service.receive(
        evidence_request_id="evidence-request-001",
        authorized_payment_intent=intent,
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="WH-001",
    )

    assert second == first
    assert store.size() == 1


def test_same_replay_identity_with_new_request_is_deduplicated(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.PAYPAL,
    )

    first = service.receive(
        evidence_request_id="request-001",
        authorized_payment_intent=intent,
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="WH-001",
    )

    replay = service.receive(
        evidence_request_id="request-002",
        authorized_payment_intent=intent,
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="WH-001",
    )

    assert replay.payment_evidence_id == first.payment_evidence_id
    assert store.size() == 1


def test_replay_identity_cannot_move_to_another_intent(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    first_intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.PAYPAL,
        customer_id="customer-001",
        order_request_id="order-request-001",
        intent_request_id="intent-request-001",
    )

    second_intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.PAYPAL,
        customer_id="customer-002",
        order_request_id="order-request-002",
        intent_request_id="intent-request-002",
    )

    service.receive(
        evidence_request_id="request-001",
        authorized_payment_intent=first_intent,
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="WH-001",
    )

    with pytest.raises(
        ValueError,
        match="replay",
    ):
        service.receive(
            evidence_request_id="request-002",
            authorized_payment_intent=second_intent,
            evidence_source=PaymentEvidenceSource.PAYPAL,
            external_evidence_id="WH-001",
        )

    assert store.size() == 1


def test_evidence_request_cannot_change_facts(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.PAYPAL,
    )

    service.receive(
        evidence_request_id="request-001",
        authorized_payment_intent=intent,
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="WH-001",
    )

    with pytest.raises(
        ValueError,
        match="evidence request",
    ):
        service.receive(
            evidence_request_id="request-001",
            authorized_payment_intent=intent,
            evidence_source=PaymentEvidenceSource.PAYPAL,
            external_evidence_id="WH-002",
        )

    assert store.size() == 1


def test_cross_rail_evidence_is_rejected(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.PAYPAL,
    )

    with pytest.raises(
        ValueError,
        match="source",
    ):
        service.receive(
            evidence_request_id="request-001",
            authorized_payment_intent=intent,
            evidence_source=(
                PaymentEvidenceSource.VND_BANK_TRANSFER
            ),
            external_evidence_id="BANK-001",
        )

    assert store.size() == 0


@pytest.mark.parametrize(
    "bad_source",
    (
        "PAYPAL",
        "VND_BANK_TRANSFER",
        "VIETQR",
        "",
        None,
    ),
)
def test_raw_or_unknown_evidence_source_is_rejected(
    tmp_path: Path,
    bad_source,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.PAYPAL,
    )

    with pytest.raises(
        TypeError,
    ):
        service.receive(
            evidence_request_id="request-001",
            authorized_payment_intent=intent,
            evidence_source=bad_source,
            external_evidence_id="WH-001",
        )

    assert store.size() == 0


@pytest.mark.parametrize(
    "bad_external_id",
    (
        "",
        "   ",
        None,
        123,
    ),
)
def test_invalid_external_evidence_id_is_rejected(
    tmp_path: Path,
    bad_external_id,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.PAYPAL,
    )

    with pytest.raises(
        (TypeError, ValueError),
    ):
        service.receive(
            evidence_request_id="request-001",
            authorized_payment_intent=intent,
            evidence_source=PaymentEvidenceSource.PAYPAL,
            external_evidence_id=bad_external_id,
        )

    assert store.size() == 0


def test_evidence_record_contains_only_normalized_binding(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.PAYPAL,
    )

    result = service.receive(
        evidence_request_id="request-001",
        authorized_payment_intent=intent,
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="WH-001",
    )

    record = store.get(
        payment_evidence_id=result.payment_evidence_id,
    )

    assert record is not None

    assert set(record.__dict__) == {
        "evidence_request_id",
        "payment_evidence_id",
        "payment_intent_id",
        "evidence_source",
        "external_evidence_id",
        "status",
    }


def test_p3_exposes_no_verification_settlement_or_activation_authority(
    tmp_path: Path,
):
    (
        service,
        store,
        _,
        _,
        _,
    ) = _built_service(tmp_path)

    forbidden = (
        "verify",
        "settle",
        "mark_paid",
        "process_callback",
        "process_webhook",
        "activate_setup",
        "activate_entitlement",
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

def test_corrupt_payment_evidence_store_fails_closed(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_evidence.json"
    )

    storage_path.write_text(
        "{not-json",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="unreadable",
    ):
        CustomerPaymentEvidenceStore(
            storage_path
        )


def test_payment_evidence_store_rejects_unknown_fields(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_evidence.json"
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
        CustomerPaymentEvidenceStore(
            storage_path
        )


def test_payment_evidence_store_rejects_duplicate_evidence_id(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_evidence.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "evidence_request_id": "request-001",
      "payment_evidence_id": "payment-evidence-001",
      "payment_intent_id": "payment-intent-001",
      "evidence_source": "PAYPAL",
      "external_evidence_id": "WH-001",
      "status": "RECEIVED"
    },
    {
      "evidence_request_id": "request-002",
      "payment_evidence_id": "payment-evidence-001",
      "payment_intent_id": "payment-intent-002",
      "evidence_source": "PAYPAL",
      "external_evidence_id": "WH-002",
      "status": "RECEIVED"
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
        match="Duplicate customer payment evidence ID",
    ):
        CustomerPaymentEvidenceStore(
            storage_path
        )


def test_payment_evidence_store_rejects_duplicate_request_id(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_evidence.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "evidence_request_id": "request-001",
      "payment_evidence_id": "payment-evidence-001",
      "payment_intent_id": "payment-intent-001",
      "evidence_source": "PAYPAL",
      "external_evidence_id": "WH-001",
      "status": "RECEIVED"
    },
    {
      "evidence_request_id": "request-001",
      "payment_evidence_id": "payment-evidence-002",
      "payment_intent_id": "payment-intent-002",
      "evidence_source": "VND_BANK_TRANSFER",
      "external_evidence_id": "BANK-001",
      "status": "RECEIVED"
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
        match="Duplicate customer payment evidence request",
    ):
        CustomerPaymentEvidenceStore(
            storage_path
        )


def test_payment_evidence_store_rejects_duplicate_replay_identity(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_evidence.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "evidence_request_id": "request-001",
      "payment_evidence_id": "payment-evidence-001",
      "payment_intent_id": "payment-intent-001",
      "evidence_source": "PAYPAL",
      "external_evidence_id": "WH-001",
      "status": "RECEIVED"
    },
    {
      "evidence_request_id": "request-002",
      "payment_evidence_id": "payment-evidence-002",
      "payment_intent_id": "payment-intent-001",
      "evidence_source": "PAYPAL",
      "external_evidence_id": "WH-001",
      "status": "RECEIVED"
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
        match="replay identity",
    ):
        CustomerPaymentEvidenceStore(
            storage_path
        )


@pytest.mark.parametrize(
    "bad_source",
    (
        "VIETQR",
        "BANK",
        "STRIPE",
        "",
    ),
)
def test_payment_evidence_store_rejects_unknown_source_on_restore(
    tmp_path: Path,
    bad_source: str,
):
    storage_path = (
        tmp_path / "customer_payment_evidence.json"
    )

    storage_path.write_text(
        (
            """
{
  "records": [
    {
      "evidence_request_id": "request-001",
      "payment_evidence_id": "payment-evidence-001",
      "payment_intent_id": "payment-intent-001",
      "evidence_source": "__SOURCE__",
      "external_evidence_id": "EXT-001",
      "status": "RECEIVED"
    }
  ],
  "version": 1
}
""".replace(
                "__SOURCE__",
                bad_source,
            ).strip()
            + "\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="invalid",
    ):
        CustomerPaymentEvidenceStore(
            storage_path
        )


@pytest.mark.parametrize(
    "bad_status",
    (
        "VERIFIED",
        "SETTLED",
        "PAID",
        "",
    ),
)
def test_payment_evidence_store_rejects_non_received_status(
    tmp_path: Path,
    bad_status: str,
):
    storage_path = (
        tmp_path / "customer_payment_evidence.json"
    )

    storage_path.write_text(
        (
            """
{
  "records": [
    {
      "evidence_request_id": "request-001",
      "payment_evidence_id": "payment-evidence-001",
      "payment_intent_id": "payment-intent-001",
      "evidence_source": "PAYPAL",
      "external_evidence_id": "WH-001",
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
        CustomerPaymentEvidenceStore(
            storage_path
        )


def test_payment_evidence_restores_replay_index(
    tmp_path: Path,
):
    (
        service,
        _,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.PAYPAL,
    )

    created = service.receive(
        evidence_request_id="request-001",
        authorized_payment_intent=intent,
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="WH-RESTORE-001",
    )

    restored = CustomerPaymentEvidenceStore(
        tmp_path / "customer_payment_evidence.json"
    )

    assert restored.is_ready()

    by_id = restored.get(
        payment_evidence_id=created.payment_evidence_id,
    )
    assert by_id is not None

    by_replay = restored.get_by_replay_identity(
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="WH-RESTORE-001",
    )

    assert by_replay == by_id


def test_payment_evidence_same_external_id_isolated_by_source(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    paypal_intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.PAYPAL,
        customer_id="customer-paypal",
        order_request_id="order-paypal",
        intent_request_id="intent-paypal",
    )

    bank_intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.VND_BANK_TRANSFER,
        customer_id="customer-bank",
        order_request_id="order-bank",
        intent_request_id="intent-bank",
    )

    paypal = service.receive(
        evidence_request_id="request-paypal",
        authorized_payment_intent=paypal_intent,
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="SAME-ID",
    )

    bank = service.receive(
        evidence_request_id="request-bank",
        authorized_payment_intent=bank_intent,
        evidence_source=(
            PaymentEvidenceSource.VND_BANK_TRANSFER
        ),
        external_evidence_id="SAME-ID",
    )

    assert (
        paypal.payment_evidence_id
        != bank.payment_evidence_id
    )
    assert store.size() == 2


def test_payment_evidence_record_has_no_sensitive_or_settlement_fields(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    intent = _create_intent(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        rail=PaymentRail.PAYPAL,
    )

    result = service.receive(
        evidence_request_id="request-001",
        authorized_payment_intent=intent,
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="WH-001",
    )

    record = store.get(
        payment_evidence_id=result.payment_evidence_id,
    )

    assert record is not None

    assert set(record.__dict__) == {
        "evidence_request_id",
        "payment_evidence_id",
        "payment_intent_id",
        "evidence_source",
        "external_evidence_id",
        "status",
    }


def test_payment_evidence_store_open_existing_requires_preprovisioned_file(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_payment_evidence.json"
    )

    store = CustomerPaymentEvidenceStore(
        storage_path
    )

    assert not storage_path.exists()
    assert not store.is_ready()

    try:
        store.open_existing()
    except RuntimeError as exc:
        assert (
            str(exc)
            == "Customer payment evidence store does not exist."
        )
    else:
        raise AssertionError(
            "Missing payment evidence store did not fail closed."
        )

    assert not storage_path.exists()
    assert not store.is_ready()


def test_payment_evidence_store_open_existing_restores_without_mutation(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_payment_evidence.json"
    )

    original = CustomerPaymentEvidenceStore(
        storage_path
    )
    original.initialize_empty()

    record = CustomerPaymentEvidenceRecord(
        evidence_request_id=(
            "open-existing-evidence-request-001"
        ),
        payment_evidence_id=(
            "open-existing-evidence-001"
        ),
        payment_intent_id="payment-intent-001",
        evidence_source=PaymentEvidenceSource.PAYPAL,
        external_evidence_id="capture-001",
        status=CustomerPaymentEvidenceStatus.RECEIVED,
    )

    original.register(
        record
    )

    before = storage_path.read_bytes()

    restored = CustomerPaymentEvidenceStore(
        storage_path
    )

    assert restored.is_ready()

    restored.open_existing()

    after = storage_path.read_bytes()

    assert after == before
    assert (
        restored.get(
            payment_evidence_id=(
                record.payment_evidence_id
            )
        )
        == record
    )
