from __future__ import annotations

from pathlib import Path

import pytest

from backend.commercial.customer_commercial_entitlement_registry import (
    CustomerCommercialEntitlement,
    CustomerCommercialEntitlementRegistry,
    CustomerCommercialEntitlementStatus,
)


def _registry(
    tmp_path: Path,
) -> CustomerCommercialEntitlementRegistry:
    registry = CustomerCommercialEntitlementRegistry(
        tmp_path / "commercial_entitlements.json"
    )
    registry.initialize_empty()
    return registry


def _entitlement(
    *,
    entitlement_id: str = "commercial-entitlement-001",
    order_id: str = "commercial-order-001",
    customer_id: str = "customer-001",
    licensed_account_cap_usd: int = 2000,
    standard_monthly_price_usd: int = 80,
    status: CustomerCommercialEntitlementStatus = (
        CustomerCommercialEntitlementStatus.ACTIVE
    ),
) -> CustomerCommercialEntitlement:
    return CustomerCommercialEntitlement(
        entitlement_id=entitlement_id,
        order_id=order_id,
        customer_id=customer_id,
        licensed_account_cap_usd=licensed_account_cap_usd,
        standard_monthly_price_usd=standard_monthly_price_usd,
        status=status,
    )


def test_entitlement_surface_is_exact_and_narrow():
    assert set(
        CustomerCommercialEntitlement.__dataclass_fields__
    ) == {
        "entitlement_id",
        "order_id",
        "customer_id",
        "licensed_account_cap_usd",
        "standard_monthly_price_usd",
        "status",
    }


def test_registers_active_purchased_commercial_entitlement(
    tmp_path: Path,
):
    registry = _registry(tmp_path)
    entitlement = _entitlement()

    stored = registry.register(
        entitlement
    )

    assert stored == entitlement
    assert (
        registry.get(
            entitlement_id="commercial-entitlement-001"
        )
        == entitlement
    )
    assert (
        registry.get_by_order_id(
            order_id="commercial-order-001"
        )
        == entitlement
    )


def test_exact_registration_retry_is_idempotent(
    tmp_path: Path,
):
    registry = _registry(tmp_path)

    first = _entitlement()
    second = _entitlement()

    assert registry.register(first) == first
    assert registry.register(second) == first
    assert registry.size() == 1


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("order_id", "commercial-order-002"),
        ("customer_id", "customer-002"),
        ("licensed_account_cap_usd", 3000),
        ("standard_monthly_price_usd", 110),
    ),
)
def test_entitlement_id_cannot_be_rebound_to_different_commercial_truth(
    tmp_path: Path,
    field: str,
    value,
):
    registry = _registry(tmp_path)

    original = _entitlement()
    registry.register(
        original
    )

    kwargs = {
        "entitlement_id": "commercial-entitlement-001",
        "order_id": "commercial-order-001",
        "customer_id": "customer-001",
        "licensed_account_cap_usd": 2000,
        "standard_monthly_price_usd": 80,
        "status": CustomerCommercialEntitlementStatus.ACTIVE,
    }
    kwargs[field] = value

    with pytest.raises(
        ValueError,
        match="entitlement",
    ):
        registry.register(
            CustomerCommercialEntitlement(
                **kwargs
            )
        )

    assert registry.size() == 1
    assert (
        registry.get(
            entitlement_id="commercial-entitlement-001"
        )
        == original
    )


def test_one_order_cannot_mint_multiple_entitlements(
    tmp_path: Path,
):
    registry = _registry(tmp_path)

    registry.register(
        _entitlement()
    )

    with pytest.raises(
        ValueError,
        match="order",
    ):
        registry.register(
            _entitlement(
                entitlement_id="commercial-entitlement-002",
            )
        )

    assert registry.size() == 1


def test_different_orders_can_have_independent_entitlements(
    tmp_path: Path,
):
    registry = _registry(tmp_path)

    first = registry.register(
        _entitlement()
    )

    second = registry.register(
        _entitlement(
            entitlement_id="commercial-entitlement-002",
            order_id="commercial-order-002",
        )
    )

    assert first != second
    assert registry.size() == 2


def test_suspend_active_entitlement(
    tmp_path: Path,
):
    registry = _registry(tmp_path)

    active = registry.register(
        _entitlement()
    )

    suspended = registry.suspend(
        entitlement_id=active.entitlement_id
    )

    assert (
        suspended.status
        is CustomerCommercialEntitlementStatus.SUSPENDED
    )
    assert not registry.is_active(
        entitlement_id=active.entitlement_id
    )


def test_suspend_is_idempotent(
    tmp_path: Path,
):
    registry = _registry(tmp_path)

    active = registry.register(
        _entitlement()
    )

    first = registry.suspend(
        entitlement_id=active.entitlement_id
    )
    second = registry.suspend(
        entitlement_id=active.entitlement_id
    )

    assert second == first
    assert (
        second.status
        is CustomerCommercialEntitlementStatus.SUSPENDED
    )


def test_suspended_entitlement_can_be_reactivated(
    tmp_path: Path,
):
    registry = _registry(tmp_path)

    active = registry.register(
        _entitlement()
    )

    registry.suspend(
        entitlement_id=active.entitlement_id
    )

    reactivated = registry.activate(
        entitlement_id=active.entitlement_id
    )

    assert (
        reactivated.status
        is CustomerCommercialEntitlementStatus.ACTIVE
    )
    assert registry.is_active(
        entitlement_id=active.entitlement_id
    )


def test_unknown_entitlement_cannot_be_activated(
    tmp_path: Path,
):
    registry = _registry(tmp_path)

    with pytest.raises(
        ValueError,
        match="entitlement",
    ):
        registry.activate(
            entitlement_id="commercial-entitlement-missing"
        )


def test_unknown_entitlement_cannot_be_suspended(
    tmp_path: Path,
):
    registry = _registry(tmp_path)

    with pytest.raises(
        ValueError,
        match="entitlement",
    ):
        registry.suspend(
            entitlement_id="commercial-entitlement-missing"
        )


def test_missing_lookup_returns_none(
    tmp_path: Path,
):
    registry = _registry(tmp_path)

    assert (
        registry.get(
            entitlement_id="commercial-entitlement-missing"
        )
        is None
    )

    assert (
        registry.get_by_order_id(
            order_id="commercial-order-missing"
        )
        is None
    )


def test_durable_active_truth_survives_restart(
    tmp_path: Path,
):
    path = (
        tmp_path
        / "commercial_entitlements.json"
    )

    registry = CustomerCommercialEntitlementRegistry(
        path
    )
    registry.initialize_empty()

    created = registry.register(
        _entitlement(
            licensed_account_cap_usd=8000,
            standard_monthly_price_usd=230,
        )
    )

    restored = CustomerCommercialEntitlementRegistry(
        path
    )

    assert restored.is_ready()
    assert (
        restored.get(
            entitlement_id=created.entitlement_id
        )
        == created
    )
    assert restored.is_active(
        entitlement_id=created.entitlement_id
    )


def test_durable_suspension_survives_restart(
    tmp_path: Path,
):
    path = (
        tmp_path
        / "commercial_entitlements.json"
    )

    registry = CustomerCommercialEntitlementRegistry(
        path
    )
    registry.initialize_empty()

    created = registry.register(
        _entitlement()
    )

    suspended = registry.suspend(
        entitlement_id=created.entitlement_id
    )

    restored = CustomerCommercialEntitlementRegistry(
        path
    )

    assert (
        restored.get(
            entitlement_id=created.entitlement_id
        )
        == suspended
    )
    assert not restored.is_active(
        entitlement_id=created.entitlement_id
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("entitlement_id", ""),
        ("order_id", ""),
        ("customer_id", ""),
        ("licensed_account_cap_usd", 0),
        ("licensed_account_cap_usd", -1),
        ("standard_monthly_price_usd", 0),
        ("standard_monthly_price_usd", -1),
    ),
)
def test_invalid_entitlement_truth_fails_closed(
    field: str,
    value,
):
    kwargs = {
        "entitlement_id": "commercial-entitlement-001",
        "order_id": "commercial-order-001",
        "customer_id": "customer-001",
        "licensed_account_cap_usd": 2000,
        "standard_monthly_price_usd": 80,
        "status": CustomerCommercialEntitlementStatus.ACTIVE,
    }
    kwargs[field] = value

    with pytest.raises(
        (TypeError, ValueError),
    ):
        CustomerCommercialEntitlement(
            **kwargs
        )


def test_status_must_be_entitlement_status_enum():
    with pytest.raises(
        TypeError,
    ):
        CustomerCommercialEntitlement(
            entitlement_id="commercial-entitlement-001",
            order_id="commercial-order-001",
            customer_id="customer-001",
            licensed_account_cap_usd=2000,
            standard_monthly_price_usd=80,
            status="ACTIVE",
        )


def test_registry_has_no_payment_setup_deployment_or_runtime_authority():
    forbidden = {
        "settle",
        "verify_payment",
        "activate_setup",
        "bind_deployment",
        "authorize_runtime",
        "issue_activation_code",
    }

    assert forbidden.isdisjoint(
        set(
            dir(
                CustomerCommercialEntitlementRegistry
            )
        )
    )
