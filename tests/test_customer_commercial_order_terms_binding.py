from __future__ import annotations

from pathlib import Path

import pytest

from backend.commercial.customer_commercial_order_terms_binding import (
    CustomerCommercialOrderTermsBindingRecord,
    CustomerCommercialOrderTermsBindingStore,
)


def _store(
    tmp_path: Path,
) -> CustomerCommercialOrderTermsBindingStore:
    store = CustomerCommercialOrderTermsBindingStore(
        tmp_path / "order_terms.json"
    )
    store.initialize_empty()
    return store


def test_registers_exact_purchased_terms_for_order(
    tmp_path: Path,
):
    store = _store(tmp_path)

    record = CustomerCommercialOrderTermsBindingRecord(
        order_id="commercial-order-001",
        customer_id="customer-001",
        licensed_account_cap_usd=2000,
        standard_monthly_price_usd=80,
    )

    stored = store.register(record)

    assert stored == record
    assert (
        store.get_by_order_id(
            order_id="commercial-order-001"
        )
        == record
    )


def test_record_surface_is_exact_and_narrow():
    assert set(
        CustomerCommercialOrderTermsBindingRecord
        .__dataclass_fields__
    ) == {
        "order_id",
        "customer_id",
        "licensed_account_cap_usd",
        "standard_monthly_price_usd",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("order_id", ""),
        ("customer_id", ""),
        ("licensed_account_cap_usd", 0),
        ("licensed_account_cap_usd", -1000),
        ("standard_monthly_price_usd", 0),
        ("standard_monthly_price_usd", -1),
    ),
)
def test_invalid_terms_fail_closed(
    field,
    value,
):
    kwargs = {
        "order_id": "commercial-order-001",
        "customer_id": "customer-001",
        "licensed_account_cap_usd": 2000,
        "standard_monthly_price_usd": 80,
    }
    kwargs[field] = value

    with pytest.raises(
        (TypeError, ValueError),
    ):
        CustomerCommercialOrderTermsBindingRecord(
            **kwargs
        )


def test_identical_retry_is_idempotent(
    tmp_path: Path,
):
    store = _store(tmp_path)

    first = CustomerCommercialOrderTermsBindingRecord(
        order_id="commercial-order-001",
        customer_id="customer-001",
        licensed_account_cap_usd=2000,
        standard_monthly_price_usd=80,
    )

    second = CustomerCommercialOrderTermsBindingRecord(
        order_id="commercial-order-001",
        customer_id="customer-001",
        licensed_account_cap_usd=2000,
        standard_monthly_price_usd=80,
    )

    assert store.register(first) == first
    assert store.register(second) == first
    assert store.size() == 1


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("customer_id", "customer-002"),
        ("licensed_account_cap_usd", 3000),
        ("standard_monthly_price_usd", 110),
    ),
)
def test_same_order_cannot_be_rebound_to_different_terms(
    tmp_path: Path,
    field,
    value,
):
    store = _store(tmp_path)

    original = CustomerCommercialOrderTermsBindingRecord(
        order_id="commercial-order-001",
        customer_id="customer-001",
        licensed_account_cap_usd=2000,
        standard_monthly_price_usd=80,
    )
    store.register(original)

    kwargs = {
        "order_id": "commercial-order-001",
        "customer_id": "customer-001",
        "licensed_account_cap_usd": 2000,
        "standard_monthly_price_usd": 80,
    }
    kwargs[field] = value

    with pytest.raises(
        ValueError,
        match="order",
    ):
        store.register(
            CustomerCommercialOrderTermsBindingRecord(
                **kwargs
            )
        )

    assert store.size() == 1
    assert (
        store.get_by_order_id(
            order_id="commercial-order-001"
        )
        == original
    )


def test_durable_terms_survive_restart(
    tmp_path: Path,
):
    path = tmp_path / "order_terms.json"

    store = CustomerCommercialOrderTermsBindingStore(
        path
    )
    store.initialize_empty()

    record = CustomerCommercialOrderTermsBindingRecord(
        order_id="commercial-order-001",
        customer_id="customer-001",
        licensed_account_cap_usd=8000,
        standard_monthly_price_usd=230,
    )

    store.register(record)

    restored = CustomerCommercialOrderTermsBindingStore(
        path
    )

    assert restored.is_ready()
    assert (
        restored.get_by_order_id(
            order_id="commercial-order-001"
        )
        == record
    )


def test_missing_order_terms_return_none(
    tmp_path: Path,
):
    store = _store(tmp_path)

    assert (
        store.get_by_order_id(
            order_id="commercial-order-missing"
        )
        is None
    )


def test_binding_owner_has_no_payment_entitlement_or_deployment_authority():
    forbidden = {
        "settle",
        "activate",
        "authorize",
        "bind_deployment",
        "create_payment_intent",
    }

    assert forbidden.isdisjoint(
        set(
            dir(
                CustomerCommercialOrderTermsBindingStore
            )
        )
    )
