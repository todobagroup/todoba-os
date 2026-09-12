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
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentService,
    CustomerPaymentIntentStore,
    PaymentRail,
)
from backend.commercial.customer_paypal_order_binding_service import (
    CustomerPayPalOrderBindingRecord,
    CustomerPayPalOrderBindingService,
    CustomerPayPalOrderBindingStatus,
    CustomerPayPalOrderBindingStore,
    PayPalOrderCreationResult,
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

    binding_store = CustomerPayPalOrderBindingStore(
        tmp_path / "customer_paypal_order_bindings.json"
    )
    binding_store.initialize_empty()

    binding_service = CustomerPayPalOrderBindingService(
        binding_store=binding_store,
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    return (
        binding_service,
        binding_store,
        intent_service,
        identity_registry,
        order_service,
    )


def _create_paypal_chain(
    *,
    intent_service,
    identity_registry,
    order_service,
    customer_id="customer-001",
    order_request_id="order-request-001",
    intent_request_id="intent-request-001",
    amount_minor=1999,
    currency="USD",
):
    customer = identity_registry.register(
        CustomerIdentity(
            customer_id=customer_id,
        )
    )

    order = order_service.create(
        order_request_id=order_request_id,
        authorized_customer=customer,
        amount_minor=amount_minor,
        currency=currency,
    )

    intent = intent_service.create(
        payment_intent_request_id=intent_request_id,
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    provider_result = PayPalOrderCreationResult(
        paypal_order_id="5O190127TN364715T",
        paypal_request_id=intent.payment_intent_id,
        custom_id=intent.payment_intent_id,
        amount_minor=order.amount_minor,
        currency=order.currency,
    )

    return order, intent, provider_result


def test_exact_paypal_order_result_creates_binding(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    order, intent, provider_result = _create_paypal_chain(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    result = service.bind(
        authorized_payment_intent=intent,
        paypal_order=provider_result,
    )

    assert result.paypal_binding_id.startswith(
        "paypal-order-binding-"
    )
    assert result.paypal_order_id == "5O190127TN364715T"
    assert result.payment_intent_id == intent.payment_intent_id
    assert result.order_id == order.order_id
    assert result.amount_minor == 1999
    assert result.currency == "USD"
    assert (
        result.status
        is CustomerPayPalOrderBindingStatus.BOUND
    )
    assert store.size() == 1


def test_identical_binding_retry_is_idempotent(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, intent, provider_result = _create_paypal_chain(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    first = service.bind(
        authorized_payment_intent=intent,
        paypal_order=provider_result,
    )

    second = service.bind(
        authorized_payment_intent=intent,
        paypal_order=provider_result,
    )

    assert second == first
    assert store.size() == 1


@pytest.mark.parametrize(
    "field,value",
    (
        ("custom_id", "payment-intent-forged"),
        ("paypal_request_id", "different-request"),
        ("amount_minor", 2000),
        ("currency", "EUR"),
    ),
)
def test_provider_result_mismatch_fails_closed(
    tmp_path: Path,
    field,
    value,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, intent, provider_result = _create_paypal_chain(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    forged = replace(
        provider_result,
        **{
            field: value,
        },
    )

    with pytest.raises(
        ValueError,
        match="PayPal",
    ):
        service.bind(
            authorized_payment_intent=intent,
            paypal_order=forged,
        )

    assert store.size() == 0


def test_non_paypal_intent_is_rejected(
    tmp_path: Path,
):
    (
        service,
        store,
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

    intent = intent_service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    provider_result = PayPalOrderCreationResult(
        paypal_order_id="5O190127TN364715T",
        paypal_request_id=intent.payment_intent_id,
        custom_id=intent.payment_intent_id,
        amount_minor=order.amount_minor,
        currency=order.currency,
    )

    with pytest.raises(
        ValueError,
        match="PAYPAL",
    ):
        service.bind(
            authorized_payment_intent=intent,
            paypal_order=provider_result,
        )

    assert store.size() == 0


def test_paypal_vnd_order_is_rejected(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, intent, provider_result = _create_paypal_chain(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        amount_minor=1_000_000,
        currency="VND",
    )

    with pytest.raises(
        ValueError,
        match="currency",
    ):
        service.bind(
            authorized_payment_intent=intent,
            paypal_order=provider_result,
        )

    assert store.size() == 0


def test_one_intent_cannot_move_to_another_paypal_order(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, intent, provider_result = _create_paypal_chain(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    service.bind(
        authorized_payment_intent=intent,
        paypal_order=provider_result,
    )

    changed = replace(
        provider_result,
        paypal_order_id="8K832279M55989614",
    )

    with pytest.raises(
        ValueError,
        match="intent",
    ):
        service.bind(
            authorized_payment_intent=intent,
            paypal_order=changed,
        )

    assert store.size() == 1


def test_paypal_order_id_cannot_move_to_another_intent(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, first_intent, first_provider = _create_paypal_chain(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        customer_id="customer-001",
        order_request_id="order-request-001",
        intent_request_id="intent-request-001",
    )

    service.bind(
        authorized_payment_intent=first_intent,
        paypal_order=first_provider,
    )

    second_order, second_intent, _ = _create_paypal_chain(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
        customer_id="customer-002",
        order_request_id="order-request-002",
        intent_request_id="intent-request-002",
    )

    replay = PayPalOrderCreationResult(
        paypal_order_id=first_provider.paypal_order_id,
        paypal_request_id=second_intent.payment_intent_id,
        custom_id=second_intent.payment_intent_id,
        amount_minor=second_order.amount_minor,
        currency=second_order.currency,
    )

    with pytest.raises(
        ValueError,
        match="PayPal order",
    ):
        service.bind(
            authorized_payment_intent=second_intent,
            paypal_order=replay,
        )

    assert store.size() == 1


def test_forged_payment_intent_result_is_rejected(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, intent, provider_result = _create_paypal_chain(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    forged_intent = replace(
        intent,
        order_id="commercial-order-forged",
    )

    with pytest.raises(
        ValueError,
        match="authoritative",
    ):
        service.bind(
            authorized_payment_intent=forged_intent,
            paypal_order=provider_result,
        )

    assert store.size() == 0


@pytest.mark.parametrize(
    "bad_amount",
    (
        0,
        -1,
        True,
        19.99,
        "1999",
    ),
)
def test_paypal_creation_result_rejects_invalid_amount(
    bad_amount,
):
    with pytest.raises(
        (TypeError, ValueError),
    ):
        PayPalOrderCreationResult(
            paypal_order_id="5O190127TN364715T",
            paypal_request_id="payment-intent-001",
            custom_id="payment-intent-001",
            amount_minor=bad_amount,
            currency="USD",
        )


def test_binding_record_contains_no_credentials_or_payment_authority(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, intent, provider_result = _create_paypal_chain(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    result = service.bind(
        authorized_payment_intent=intent,
        paypal_order=provider_result,
    )

    record = store.get(
        paypal_binding_id=result.paypal_binding_id,
    )

    assert record is not None

    assert set(record.__dict__) == {
        "paypal_binding_id",
        "paypal_order_id",
        "paypal_request_id",
        "payment_intent_id",
        "order_id",
        "amount_minor",
        "currency",
        "status",
    }


def test_p5a1_exposes_no_network_verification_or_settlement_authority(
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
        "get_access_token",
        "create_order_http",
        "verify_webhook",
        "receive_evidence",
        "settle",
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

def test_paypal_binding_store_corrupt_json_fails_closed(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_paypal_order_bindings.json"
    )

    storage_path.write_text(
        "{not-json",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="unreadable",
    ):
        CustomerPayPalOrderBindingStore(
            storage_path
        )


def test_paypal_binding_store_rejects_unknown_fields(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_paypal_order_bindings.json"
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
        CustomerPayPalOrderBindingStore(
            storage_path
        )


def test_paypal_binding_store_rejects_duplicate_binding_id(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_paypal_order_bindings.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "paypal_binding_id": "paypal-order-binding-001",
      "paypal_order_id": "PP-ORDER-001",
      "paypal_request_id": "payment-intent-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "amount_minor": 1999,
      "currency": "USD",
      "status": "BOUND"
    },
    {
      "paypal_binding_id": "paypal-order-binding-001",
      "paypal_order_id": "PP-ORDER-002",
      "paypal_request_id": "payment-intent-002",
      "payment_intent_id": "payment-intent-002",
      "order_id": "commercial-order-002",
      "amount_minor": 2999,
      "currency": "USD",
      "status": "BOUND"
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
        match="Duplicate PayPal binding ID",
    ):
        CustomerPayPalOrderBindingStore(
            storage_path
        )


def test_paypal_binding_store_rejects_duplicate_payment_intent(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_paypal_order_bindings.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "paypal_binding_id": "paypal-order-binding-001",
      "paypal_order_id": "PP-ORDER-001",
      "paypal_request_id": "payment-intent-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "amount_minor": 1999,
      "currency": "USD",
      "status": "BOUND"
    },
    {
      "paypal_binding_id": "paypal-order-binding-002",
      "paypal_order_id": "PP-ORDER-002",
      "paypal_request_id": "payment-intent-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "amount_minor": 1999,
      "currency": "USD",
      "status": "BOUND"
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
        match="Duplicate PayPal binding payment intent",
    ):
        CustomerPayPalOrderBindingStore(
            storage_path
        )


def test_paypal_binding_store_rejects_duplicate_paypal_order(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_paypal_order_bindings.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "paypal_binding_id": "paypal-order-binding-001",
      "paypal_order_id": "PP-ORDER-001",
      "paypal_request_id": "payment-intent-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "amount_minor": 1999,
      "currency": "USD",
      "status": "BOUND"
    },
    {
      "paypal_binding_id": "paypal-order-binding-002",
      "paypal_order_id": "PP-ORDER-001",
      "paypal_request_id": "payment-intent-002",
      "payment_intent_id": "payment-intent-002",
      "order_id": "commercial-order-002",
      "amount_minor": 2999,
      "currency": "USD",
      "status": "BOUND"
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
        match="Duplicate PayPal order ID",
    ):
        CustomerPayPalOrderBindingStore(
            storage_path
        )


@pytest.mark.parametrize(
    "bad_status",
    (
        "PENDING",
        "CREATED",
        "COMPLETED",
        "SETTLED",
        "",
    ),
)
def test_paypal_binding_store_rejects_non_bound_status(
    tmp_path: Path,
    bad_status: str,
):
    storage_path = (
        tmp_path / "customer_paypal_order_bindings.json"
    )

    storage_path.write_text(
        (
            """
{
  "records": [
    {
      "paypal_binding_id": "paypal-order-binding-001",
      "paypal_order_id": "PP-ORDER-001",
      "paypal_request_id": "payment-intent-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "amount_minor": 1999,
      "currency": "USD",
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
        CustomerPayPalOrderBindingStore(
            storage_path
        )


def test_paypal_binding_restore_rejects_unsupported_payment_currency(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_paypal_order_bindings.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "paypal_binding_id": "paypal-order-binding-001",
      "paypal_order_id": "PP-ORDER-001",
      "paypal_request_id": "payment-intent-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "amount_minor": 1000000,
      "currency": "VND",
      "status": "BOUND"
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
        match="invalid",
    ):
        CustomerPayPalOrderBindingStore(
            storage_path
        )


def test_paypal_binding_restore_rejects_request_intent_mismatch(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_paypal_order_bindings.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "paypal_binding_id": "paypal-order-binding-001",
      "paypal_order_id": "PP-ORDER-001",
      "paypal_request_id": "payment-intent-attacker",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "amount_minor": 1999,
      "currency": "USD",
      "status": "BOUND"
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
        match="invalid",
    ):
        CustomerPayPalOrderBindingStore(
            storage_path
        )


def test_paypal_binding_restore_preserves_indexes(
    tmp_path: Path,
):
    (
        service,
        _,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, intent, provider_result = _create_paypal_chain(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    created = service.bind(
        authorized_payment_intent=intent,
        paypal_order=provider_result,
    )

    restored = CustomerPayPalOrderBindingStore(
        tmp_path / "customer_paypal_order_bindings.json"
    )

    assert restored.is_ready()

    assert (
        restored.get(
            paypal_binding_id=created.paypal_binding_id,
        )
        == created
    )

    assert (
        restored.get_by_payment_intent_id(
            payment_intent_id=intent.payment_intent_id,
        )
        == created
    )

    assert (
        restored.get_by_paypal_order_id(
            paypal_order_id=provider_result.paypal_order_id,
        )
        == created
    )


def test_paypal_binding_persists_no_custom_id_or_secrets(
    tmp_path: Path,
):
    (
        service,
        store,
        intent_service,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    _, intent, provider_result = _create_paypal_chain(
        intent_service=intent_service,
        identity_registry=identity_registry,
        order_service=order_service,
    )

    created = service.bind(
        authorized_payment_intent=intent,
        paypal_order=provider_result,
    )

    record = store.get(
        paypal_binding_id=created.paypal_binding_id,
    )

    assert record is not None
    assert "custom_id" not in record.__dict__
    assert "client_id" not in record.__dict__
    assert "client_secret" not in record.__dict__
    assert "access_token" not in record.__dict__
    assert "webhook_signature" not in record.__dict__
    assert "raw_payload" not in record.__dict__


def test_paypal_order_binding_store_open_existing_requires_preprovisioned_file(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_paypal_order_bindings.json"
    )

    store = CustomerPayPalOrderBindingStore(
        storage_path
    )

    assert not storage_path.exists()
    assert not store.is_ready()

    try:
        store.open_existing()
    except RuntimeError as exc:
        assert (
            str(exc)
            == "Customer PayPal order binding store does not exist."
        )
    else:
        raise AssertionError(
            "Missing PayPal order binding store did not fail closed."
        )

    assert not storage_path.exists()
    assert not store.is_ready()


def test_paypal_order_binding_store_open_existing_restores_without_mutation(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_paypal_order_bindings.json"
    )

    original = CustomerPayPalOrderBindingStore(
        storage_path
    )
    original.initialize_empty()

    record = CustomerPayPalOrderBindingRecord(
        paypal_binding_id=(
            "open-existing-paypal-binding-001"
        ),
        paypal_order_id="paypal-order-001",
        paypal_request_id="payment-intent-001",
        payment_intent_id="payment-intent-001",
        order_id="order-001",
        amount_minor=1000,
        currency="USD",
        status=CustomerPayPalOrderBindingStatus.BOUND,
    )

    original.register(
        record
    )

    before = storage_path.read_bytes()

    restored = CustomerPayPalOrderBindingStore(
        storage_path
    )

    assert restored.is_ready()

    restored.open_existing()

    after = storage_path.read_bytes()

    assert after == before
