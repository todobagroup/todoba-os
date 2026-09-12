from pathlib import Path

import pytest

from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderRecord,
    CustomerCommercialOrderService,
    CustomerCommercialOrderStatus,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)


def _identity_registry(
    tmp_path: Path,
) -> CustomerIdentityRegistry:
    registry = CustomerIdentityRegistry(
        tmp_path / "customer_identities.json"
    )
    registry.initialize_empty()
    return registry


def _built_service(
    tmp_path: Path,
) -> tuple[
    CustomerCommercialOrderService,
    CustomerCommercialOrderStore,
    CustomerIdentityRegistry,
]:
    identity_registry = _identity_registry(tmp_path)

    order_store = CustomerCommercialOrderStore(
        tmp_path / "customer_commercial_orders.json"
    )
    order_store.initialize_empty()

    service = CustomerCommercialOrderService(
        order_store=order_store,
        customer_identity_registry=identity_registry,
    )

    return (
        service,
        order_store,
        identity_registry,
    )


def test_create_commercial_order_from_authoritative_customer(
    tmp_path: Path,
):
    (
        service,
        order_store,
        identity_registry,
    ) = _built_service(tmp_path)

    customer = identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001",
        )
    )

    result = service.create(
        order_request_id="order-request-001",
        authorized_customer=customer,
        amount_minor=1_000_000,
        currency="vnd",
    )

    assert result.order_request_id == "order-request-001"
    assert result.order_id.startswith("commercial-order-")
    assert result.customer_id == "customer-001"
    assert result.amount_minor == 1_000_000
    assert result.currency == "VND"
    assert result.status is CustomerCommercialOrderStatus.PENDING

    stored = order_store.get(
        order_id=result.order_id,
    )

    assert stored is not None
    assert stored.order_id == result.order_id
    assert stored.customer_id == "customer-001"
    assert stored.amount_minor == 1_000_000
    assert stored.currency == "VND"
    assert stored.status is CustomerCommercialOrderStatus.PENDING


def test_identical_order_request_retry_is_idempotent(
    tmp_path: Path,
):
    (
        service,
        order_store,
        identity_registry,
    ) = _built_service(tmp_path)

    customer = identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001",
        )
    )

    first = service.create(
        order_request_id="order-request-001",
        authorized_customer=customer,
        amount_minor=1_000_000,
        currency="VND",
    )

    second = service.create(
        order_request_id="order-request-001",
        authorized_customer=customer,
        amount_minor=1_000_000,
        currency="VND",
    )

    assert second == first
    assert order_store.size() == 1


@pytest.mark.parametrize(
    (
        "changed_field",
        "changed_value",
    ),
    (
        ("amount_minor", 999_999),
        ("currency", "USD"),
    ),
)
def test_order_request_reuse_with_changed_commercial_fact_fails_closed(
    tmp_path: Path,
    changed_field: str,
    changed_value,
):
    (
        service,
        order_store,
        identity_registry,
    ) = _built_service(tmp_path)

    customer = identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001",
        )
    )

    service.create(
        order_request_id="order-request-001",
        authorized_customer=customer,
        amount_minor=1_000_000,
        currency="VND",
    )

    kwargs = {
        "order_request_id": "order-request-001",
        "authorized_customer": customer,
        "amount_minor": 1_000_000,
        "currency": "VND",
    }
    kwargs[changed_field] = changed_value

    with pytest.raises(
        ValueError,
        match="order request",
    ):
        service.create(**kwargs)

    assert order_store.size() == 1


def test_order_request_cannot_move_to_another_customer(
    tmp_path: Path,
):
    (
        service,
        order_store,
        identity_registry,
    ) = _built_service(tmp_path)

    customer_a = identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001",
        )
    )
    customer_b = identity_registry.register(
        CustomerIdentity(
            customer_id="customer-002",
        )
    )

    service.create(
        order_request_id="order-request-001",
        authorized_customer=customer_a,
        amount_minor=1_000_000,
        currency="VND",
    )

    with pytest.raises(
        ValueError,
        match="order request",
    ):
        service.create(
            order_request_id="order-request-001",
            authorized_customer=customer_b,
            amount_minor=1_000_000,
            currency="VND",
        )

    assert order_store.size() == 1


def test_unregistered_customer_identity_is_rejected(
    tmp_path: Path,
):
    (
        service,
        order_store,
        _,
    ) = _built_service(tmp_path)

    forged_customer = CustomerIdentity(
        customer_id="customer-forged",
    )

    with pytest.raises(
        ValueError,
        match="Customer",
    ):
        service.create(
            order_request_id="order-request-001",
            authorized_customer=forged_customer,
            amount_minor=1_000_000,
            currency="VND",
        )

    assert order_store.size() == 0


@pytest.mark.parametrize(
    "amount_minor",
    (
        0,
        -1,
        10.5,
        True,
        "1000000",
    ),
)
def test_invalid_amount_minor_is_rejected(
    tmp_path: Path,
    amount_minor,
):
    (
        service,
        order_store,
        identity_registry,
    ) = _built_service(tmp_path)

    customer = identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001",
        )
    )

    with pytest.raises(
        (TypeError, ValueError),
    ):
        service.create(
            order_request_id="order-request-001",
            authorized_customer=customer,
            amount_minor=amount_minor,
            currency="VND",
        )

    assert order_store.size() == 0


@pytest.mark.parametrize(
    "currency",
    (
        "",
        "VN",
        "VND1",
        "V ND",
        123,
    ),
)
def test_invalid_currency_is_rejected(
    tmp_path: Path,
    currency,
):
    (
        service,
        order_store,
        identity_registry,
    ) = _built_service(tmp_path)

    customer = identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001",
        )
    )

    with pytest.raises(
        (TypeError, ValueError),
    ):
        service.create(
            order_request_id="order-request-001",
            authorized_customer=customer,
            amount_minor=1_000_000,
            currency=currency,
        )

    assert order_store.size() == 0


def test_durable_order_restores_exact_commercial_truth(
    tmp_path: Path,
):
    (
        service,
        _,
        identity_registry,
    ) = _built_service(tmp_path)

    customer = identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001",
        )
    )

    created = service.create(
        order_request_id="order-request-001",
        authorized_customer=customer,
        amount_minor=1_000_000,
        currency="VND",
    )

    restored = CustomerCommercialOrderStore(
        tmp_path / "customer_commercial_orders.json"
    )

    assert restored.is_ready()

    record = restored.get(
        order_id=created.order_id,
    )

    assert record is not None
    assert record.order_request_id == "order-request-001"
    assert record.customer_id == "customer-001"
    assert record.amount_minor == 1_000_000
    assert record.currency == "VND"
    assert record.status is CustomerCommercialOrderStatus.PENDING


def test_p1_owner_exposes_no_payment_settlement_or_activation_authority(
    tmp_path: Path,
):
    (
        service,
        order_store,
        _,
    ) = _built_service(tmp_path)

    forbidden_methods = (
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
        order_store,
    ):
        for method_name in forbidden_methods:
            assert not hasattr(
                owner,
                method_name,
            )


def test_corrupt_order_store_fails_closed(
    tmp_path: Path,
):
    storage_path = (
        tmp_path
        / "customer_commercial_orders.json"
    )

    storage_path.write_text(
        "{not-json",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="unreadable",
    ):
        CustomerCommercialOrderStore(
            storage_path
        )


def test_order_store_rejects_unknown_fields(
    tmp_path: Path,
):
    storage_path = (
        tmp_path
        / "customer_commercial_orders.json"
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
        CustomerCommercialOrderStore(
            storage_path
        )


def test_order_store_rejects_duplicate_order_id(
    tmp_path: Path,
):
    storage_path = (
        tmp_path
        / "customer_commercial_orders.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "amount_minor": 1000000,
      "currency": "VND",
      "customer_id": "customer-001",
      "order_id": "commercial-order-001",
      "order_request_id": "request-001",
      "status": "PENDING"
    },
    {
      "amount_minor": 1000000,
      "currency": "VND",
      "customer_id": "customer-001",
      "order_id": "commercial-order-001",
      "order_request_id": "request-002",
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
        match="Duplicate customer commercial order ID",
    ):
        CustomerCommercialOrderStore(
            storage_path
        )


def test_order_store_rejects_duplicate_order_request_id(
    tmp_path: Path,
):
    storage_path = (
        tmp_path
        / "customer_commercial_orders.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "amount_minor": 1000000,
      "currency": "VND",
      "customer_id": "customer-001",
      "order_id": "commercial-order-001",
      "order_request_id": "request-001",
      "status": "PENDING"
    },
    {
      "amount_minor": 1000000,
      "currency": "VND",
      "customer_id": "customer-001",
      "order_id": "commercial-order-002",
      "order_request_id": "request-001",
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
        match="Duplicate customer commercial order request",
    ):
        CustomerCommercialOrderStore(
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
def test_order_store_rejects_non_pending_status(
    tmp_path: Path,
    bad_status: str,
):
    storage_path = (
        tmp_path
        / "customer_commercial_orders.json"
    )

    storage_path.write_text(
        (
            """
{
  "records": [
    {
      "amount_minor": 1000000,
      "currency": "VND",
      "customer_id": "customer-001",
      "order_id": "commercial-order-001",
      "order_request_id": "request-001",
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
        CustomerCommercialOrderStore(
            storage_path
        )


def test_order_store_rejects_zero_amount_on_restore(
    tmp_path: Path,
):
    storage_path = (
        tmp_path
        / "customer_commercial_orders.json"
    )

    storage_path.write_text(
        """
{
  "records": [
    {
      "amount_minor": 0,
      "currency": "VND",
      "customer_id": "customer-001",
      "order_id": "commercial-order-001",
      "order_request_id": "request-001",
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
        match="invalid",
    ):
        CustomerCommercialOrderStore(
            storage_path
        )


def test_order_result_contains_no_payment_provider_data(
    tmp_path: Path,
):
    (
        service,
        _,
        identity_registry,
    ) = _built_service(tmp_path)

    customer = identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001",
        )
    )

    result = service.create(
        order_request_id="order-request-001",
        authorized_customer=customer,
        amount_minor=1_000_000,
        currency="VND",
    )

    assert set(
        result.__dict__
    ) == {
        "order_request_id",
        "order_id",
        "customer_id",
        "amount_minor",
        "currency",
        "status",
    }


def test_order_store_open_existing_requires_preprovisioned_file(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_commercial_orders.json"
    )

    store = CustomerCommercialOrderStore(
        storage_path
    )

    assert not storage_path.exists()
    assert not store.is_ready()

    try:
        store.open_existing()
    except RuntimeError as exc:
        assert (
            str(exc)
            == "Customer commercial order store does not exist."
        )
    else:
        raise AssertionError(
            "Missing commercial order store did not fail closed."
        )

    assert not storage_path.exists()
    assert not store.is_ready()


def test_order_store_open_existing_restores_without_mutation(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "customer_commercial_orders.json"
    )

    original = CustomerCommercialOrderStore(
        storage_path
    )
    original.initialize_empty()

    record = CustomerCommercialOrderRecord(
        order_request_id="open-existing-request-001",
        order_id="open-existing-order-001",
        customer_id="customer-001",
        amount_minor=1000,
        currency="VND",
        status=CustomerCommercialOrderStatus.PENDING,
    )

    original.register(
        record
    )

    before = storage_path.read_bytes()

    restored = CustomerCommercialOrderStore(
        storage_path
    )

    assert restored.is_ready()

    restored.open_existing()

    after = storage_path.read_bytes()

    assert after == before
    assert (
        restored.get(
            order_id=record.order_id
        )
        == record
    )
