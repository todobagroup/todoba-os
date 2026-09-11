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
    CustomerPaymentIntentStatus,
    CustomerPaymentIntentStore,
    PaymentRail,
)


def _order_sources(
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

    return (
        identity_registry,
        order_store,
        order_service,
    )


def _built_service(
    tmp_path: Path,
):
    (
        identity_registry,
        order_store,
        order_service,
    ) = _order_sources(tmp_path)

    intent_store = CustomerPaymentIntentStore(
        tmp_path / "customer_payment_intents.json"
    )
    intent_store.initialize_empty()

    service = CustomerPaymentIntentService(
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    return (
        service,
        intent_store,
        identity_registry,
        order_service,
    )


def _create_order(
    *,
    identity_registry,
    order_service,
    request_id: str = "order-request-001",
    customer_id: str = "customer-001",
):
    customer = identity_registry.register(
        CustomerIdentity(
            customer_id=customer_id,
        )
    )

    return order_service.create(
        order_request_id=request_id,
        authorized_customer=customer,
        amount_minor=1_000_000,
        currency="VND",
    )


def test_create_paypal_intent_from_authoritative_order(
    tmp_path: Path,
):
    (
        service,
        store,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    order = _create_order(
        identity_registry=identity_registry,
        order_service=order_service,
    )

    result = service.create(
        payment_intent_request_id=(
            "payment-intent-request-001"
        ),
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    assert result.payment_intent_id.startswith(
        "payment-intent-"
    )
    assert (
        result.payment_intent_request_id
        == "payment-intent-request-001"
    )
    assert result.order_id == order.order_id
    assert result.payment_rail is PaymentRail.PAYPAL
    assert (
        result.status
        is CustomerPaymentIntentStatus.PENDING
    )

    stored = store.get(
        payment_intent_id=result.payment_intent_id,
    )

    assert stored is not None
    assert stored.order_id == order.order_id
    assert stored.payment_rail is PaymentRail.PAYPAL


def test_vnd_bank_transfer_is_supported(
    tmp_path: Path,
):
    (
        service,
        _,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    order = _create_order(
        identity_registry=identity_registry,
        order_service=order_service,
    )

    result = service.create(
        payment_intent_request_id=(
            "payment-intent-request-001"
        ),
        authorized_order=order,
        payment_rail=(
            PaymentRail.VND_BANK_TRANSFER
        ),
    )

    assert (
        result.payment_rail
        is PaymentRail.VND_BANK_TRANSFER
    )


def test_identical_payment_intent_retry_is_idempotent(
    tmp_path: Path,
):
    (
        service,
        store,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    order = _create_order(
        identity_registry=identity_registry,
        order_service=order_service,
    )

    first = service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    second = service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    assert second == first
    assert store.size() == 1


def test_intent_request_cannot_change_rail(
    tmp_path: Path,
):
    (
        service,
        store,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    order = _create_order(
        identity_registry=identity_registry,
        order_service=order_service,
    )

    service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    with pytest.raises(
        ValueError,
        match="payment intent request",
    ):
        service.create(
            payment_intent_request_id="intent-request-001",
            authorized_order=order,
            payment_rail=(
                PaymentRail.VND_BANK_TRANSFER
            ),
        )

    assert store.size() == 1


def test_intent_request_cannot_move_to_another_order(
    tmp_path: Path,
):
    (
        service,
        store,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    first_order = _create_order(
        identity_registry=identity_registry,
        order_service=order_service,
        request_id="order-request-001",
        customer_id="customer-001",
    )

    second_order = _create_order(
        identity_registry=identity_registry,
        order_service=order_service,
        request_id="order-request-002",
        customer_id="customer-002",
    )

    service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=first_order,
        payment_rail=PaymentRail.PAYPAL,
    )

    with pytest.raises(
        ValueError,
        match="payment intent request",
    ):
        service.create(
            payment_intent_request_id="intent-request-001",
            authorized_order=second_order,
            payment_rail=PaymentRail.PAYPAL,
        )

    assert store.size() == 1


def test_forged_order_result_is_rejected(
    tmp_path: Path,
):
    from backend.commercial.customer_commercial_order_service import (
        CustomerCommercialOrderResult,
        CustomerCommercialOrderStatus,
    )

    (
        service,
        store,
        _,
        _,
    ) = _built_service(tmp_path)

    forged = CustomerCommercialOrderResult(
        order_request_id="forged-request",
        order_id="commercial-order-forged",
        customer_id="customer-forged",
        amount_minor=1,
        currency="VND",
        status=CustomerCommercialOrderStatus.PENDING,
    )

    with pytest.raises(
        ValueError,
        match="authoritative",
    ):
        service.create(
            payment_intent_request_id="intent-request-001",
            authorized_order=forged,
            payment_rail=PaymentRail.PAYPAL,
        )

    assert store.size() == 0


@pytest.mark.parametrize(
    "bad_rail",
    (
        "PAYPAL",
        "VIETQR",
        "BANK",
        "",
        None,
    ),
)
def test_raw_or_unknown_payment_rail_is_rejected(
    tmp_path: Path,
    bad_rail,
):
    (
        service,
        store,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    order = _create_order(
        identity_registry=identity_registry,
        order_service=order_service,
    )

    with pytest.raises(
        TypeError,
    ):
        service.create(
            payment_intent_request_id="intent-request-001",
            authorized_order=order,
            payment_rail=bad_rail,
        )

    assert store.size() == 0


def test_same_order_can_have_separate_intents_for_different_rails(
    tmp_path: Path,
):
    (
        service,
        store,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    order = _create_order(
        identity_registry=identity_registry,
        order_service=order_service,
    )

    paypal = service.create(
        payment_intent_request_id="intent-request-paypal",
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    bank = service.create(
        payment_intent_request_id="intent-request-bank",
        authorized_order=order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    assert paypal.payment_intent_id != bank.payment_intent_id
    assert store.size() == 2


def test_payment_intent_persists_only_binding_not_order_money(
    tmp_path: Path,
):
    (
        service,
        store,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    order = _create_order(
        identity_registry=identity_registry,
        order_service=order_service,
    )

    result = service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    record = store.get(
        payment_intent_id=result.payment_intent_id,
    )

    assert record is not None

    assert set(record.__dict__) == {
        "payment_intent_request_id",
        "payment_intent_id",
        "order_id",
        "payment_rail",
        "status",
    }


def test_p2_exposes_no_settlement_or_activation_authority(
    tmp_path: Path,
):
    (
        service,
        store,
        _,
        _,
    ) = _built_service(tmp_path)

    forbidden = (
        "settle",
        "mark_paid",
        "verify_payment",
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

def test_corrupt_payment_intent_store_fails_closed(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_intents.json"
    )

    storage_path.write_text(
        "{not-json",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="unreadable",
    ):
        CustomerPaymentIntentStore(
            storage_path
        )


def test_payment_intent_store_rejects_unknown_fields(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_intents.json"
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
        CustomerPaymentIntentStore(
            storage_path
        )


def test_payment_intent_store_rejects_duplicate_intent_id(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_intents.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "payment_intent_request_id": "request-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "payment_rail": "PAYPAL",
      "status": "PENDING"
    },
    {
      "payment_intent_request_id": "request-002",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-002",
      "payment_rail": "PAYPAL",
      "status": "PENDING"
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
        match="Duplicate customer payment intent ID",
    ):
        CustomerPaymentIntentStore(
            storage_path
        )


def test_payment_intent_store_rejects_duplicate_request_id(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_intents.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "payment_intent_request_id": "request-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "payment_rail": "PAYPAL",
      "status": "PENDING"
    },
    {
      "payment_intent_request_id": "request-001",
      "payment_intent_id": "payment-intent-002",
      "order_id": "commercial-order-002",
      "payment_rail": "VND_BANK_TRANSFER",
      "status": "PENDING"
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
        match="Duplicate customer payment intent request",
    ):
        CustomerPaymentIntentStore(
            storage_path
        )


@pytest.mark.parametrize(
    "bad_rail",
    (
        "VIETQR",
        "BANK",
        "STRIPE",
        "",
    ),
)
def test_payment_intent_store_rejects_unknown_rail_on_restore(
    tmp_path: Path,
    bad_rail: str,
):
    storage_path = (
        tmp_path / "customer_payment_intents.json"
    )

    storage_path.write_text(
        (
            """
{
  "records": [
    {
      "payment_intent_request_id": "request-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "payment_rail": "__RAIL__",
      "status": "PENDING"
    }
  ],
  "version": 1
}
""".replace(
                "__RAIL__",
                bad_rail,
            ).strip()
            + "\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="invalid",
    ):
        CustomerPaymentIntentStore(
            storage_path
        )


@pytest.mark.parametrize(
    "bad_status",
    (
        "PAID",
        "SETTLED",
        "ACTIVE",
        "",
    ),
)
def test_payment_intent_store_rejects_non_pending_status(
    tmp_path: Path,
    bad_status: str,
):
    storage_path = (
        tmp_path / "customer_payment_intents.json"
    )

    storage_path.write_text(
        (
            """
{
  "records": [
    {
      "payment_intent_request_id": "request-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "payment_rail": "PAYPAL",
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
        CustomerPaymentIntentStore(
            storage_path
        )


def test_payment_intent_restores_exact_binding(
    tmp_path: Path,
):
    (
        service,
        _,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    order = _create_order(
        identity_registry=identity_registry,
        order_service=order_service,
    )

    created = service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    restored = CustomerPaymentIntentStore(
        tmp_path / "customer_payment_intents.json"
    )

    assert restored.is_ready()

    record = restored.get(
        payment_intent_id=created.payment_intent_id,
    )

    assert record is not None
    assert (
        record.payment_intent_request_id
        == "intent-request-001"
    )
    assert record.order_id == order.order_id
    assert record.payment_rail is PaymentRail.PAYPAL
    assert (
        record.status
        is CustomerPaymentIntentStatus.PENDING
    )


def test_payment_intent_result_contains_no_money_or_provider_evidence(
    tmp_path: Path,
):
    (
        service,
        _,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    order = _create_order(
        identity_registry=identity_registry,
        order_service=order_service,
    )

    result = service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    assert set(
        result.__dict__
    ) == {
        "payment_intent_request_id",
        "payment_intent_id",
        "order_id",
        "payment_rail",
        "status",
    }

def test_corrupt_payment_intent_store_fails_closed(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_intents.json"
    )

    storage_path.write_text(
        "{not-json",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="unreadable",
    ):
        CustomerPaymentIntentStore(
            storage_path
        )


def test_payment_intent_store_rejects_unknown_fields(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_intents.json"
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
        CustomerPaymentIntentStore(
            storage_path
        )


def test_payment_intent_store_rejects_duplicate_intent_id(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_intents.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "payment_intent_request_id": "request-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "payment_rail": "PAYPAL",
      "status": "PENDING"
    },
    {
      "payment_intent_request_id": "request-002",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-002",
      "payment_rail": "PAYPAL",
      "status": "PENDING"
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
        match="Duplicate customer payment intent ID",
    ):
        CustomerPaymentIntentStore(
            storage_path
        )


def test_payment_intent_store_rejects_duplicate_request_id(
    tmp_path: Path,
):
    storage_path = (
        tmp_path / "customer_payment_intents.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "payment_intent_request_id": "request-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "payment_rail": "PAYPAL",
      "status": "PENDING"
    },
    {
      "payment_intent_request_id": "request-001",
      "payment_intent_id": "payment-intent-002",
      "order_id": "commercial-order-002",
      "payment_rail": "VND_BANK_TRANSFER",
      "status": "PENDING"
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
        match="Duplicate customer payment intent request",
    ):
        CustomerPaymentIntentStore(
            storage_path
        )


@pytest.mark.parametrize(
    "bad_rail",
    (
        "VIETQR",
        "BANK",
        "STRIPE",
        "",
    ),
)
def test_payment_intent_store_rejects_unknown_rail_on_restore(
    tmp_path: Path,
    bad_rail: str,
):
    storage_path = (
        tmp_path / "customer_payment_intents.json"
    )

    storage_path.write_text(
        (
            """
{
  "records": [
    {
      "payment_intent_request_id": "request-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "payment_rail": "__RAIL__",
      "status": "PENDING"
    }
  ],
  "version": 1
}
""".replace(
                "__RAIL__",
                bad_rail,
            ).strip()
            + "\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="invalid",
    ):
        CustomerPaymentIntentStore(
            storage_path
        )


@pytest.mark.parametrize(
    "bad_status",
    (
        "PAID",
        "SETTLED",
        "ACTIVE",
        "",
    ),
)
def test_payment_intent_store_rejects_non_pending_status(
    tmp_path: Path,
    bad_status: str,
):
    storage_path = (
        tmp_path / "customer_payment_intents.json"
    )

    storage_path.write_text(
        (
            """
{
  "records": [
    {
      "payment_intent_request_id": "request-001",
      "payment_intent_id": "payment-intent-001",
      "order_id": "commercial-order-001",
      "payment_rail": "PAYPAL",
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
        CustomerPaymentIntentStore(
            storage_path
        )


def test_payment_intent_restores_exact_binding(
    tmp_path: Path,
):
    (
        service,
        _,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    order = _create_order(
        identity_registry=identity_registry,
        order_service=order_service,
    )

    created = service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    restored = CustomerPaymentIntentStore(
        tmp_path / "customer_payment_intents.json"
    )

    assert restored.is_ready()

    record = restored.get(
        payment_intent_id=created.payment_intent_id,
    )

    assert record is not None
    assert (
        record.payment_intent_request_id
        == "intent-request-001"
    )
    assert record.order_id == order.order_id
    assert record.payment_rail is PaymentRail.PAYPAL
    assert (
        record.status
        is CustomerPaymentIntentStatus.PENDING
    )


def test_payment_intent_result_contains_no_money_or_provider_evidence(
    tmp_path: Path,
):
    (
        service,
        _,
        identity_registry,
        order_service,
    ) = _built_service(tmp_path)

    order = _create_order(
        identity_registry=identity_registry,
        order_service=order_service,
    )

    result = service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    assert set(
        result.__dict__
    ) == {
        "payment_intent_request_id",
        "payment_intent_id",
        "order_id",
        "payment_rail",
        "status",
    }
