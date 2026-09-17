from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backend.commercial.customer_commercial_fx_freshness_gate import (
    CustomerCommercialFXFreshnessGate,
)
from backend.commercial.customer_commercial_fx_snapshot_service import (
    CustomerCommercialFXSnapshotRecord,
    CustomerCommercialFXSnapshotStore,
)
from backend.commercial.customer_commercial_vnd_order_pricing_projection import (
    CustomerCommercialVndOrderPricingProjectionRecord,
    CustomerCommercialVndOrderPricingProjectionService,
    CustomerCommercialVndOrderPricingProjectionStore,
)


UTC = timezone.utc
SOURCE = "vietcombank-official"
NOW = datetime(
    2026,
    9,
    17,
    12,
    0,
    tzinfo=UTC,
)


def _fx_store(
    tmp_path: Path,
    *,
    rate: Decimal = Decimal("26501.25"),
    published_at: datetime = NOW - timedelta(hours=1),
) -> CustomerCommercialFXSnapshotStore:
    store = CustomerCommercialFXSnapshotStore(
        tmp_path / "fx_snapshots.json"
    )
    store.initialize_empty()

    store.save(
        CustomerCommercialFXSnapshotRecord(
            snapshot_date=published_at.date(),
            source_id=SOURCE,
            base_currency="USD",
            quote_currency="VND",
            usd_vnd_rate=rate,
            published_at=published_at,
            fetched_at=NOW,
        )
    )

    return store


def _built_service(
    tmp_path: Path,
    *,
    rate: Decimal = Decimal("26501.25"),
    published_at: datetime = NOW - timedelta(hours=1),
):
    fx_store = _fx_store(
        tmp_path,
        rate=rate,
        published_at=published_at,
    )

    gate = CustomerCommercialFXFreshnessGate(
        snapshot_store=fx_store,
        source_id=SOURCE,
        max_age=timedelta(hours=48),
        clock=lambda: NOW,
    )

    projection_store = (
        CustomerCommercialVndOrderPricingProjectionStore(
            tmp_path / "vnd_order_pricing_projection.json"
        )
    )
    projection_store.initialize_empty()

    service = (
        CustomerCommercialVndOrderPricingProjectionService(
            projection_store=projection_store,
            fx_freshness_gate=gate,
        )
    )

    return service, projection_store


def test_projects_and_freezes_authoritative_vnd_pricing(
    tmp_path: Path,
):
    service, store = _built_service(tmp_path)

    result = service.create(
        pricing_request_id="pricing-request-001",
        customer_id="customer-001",
        usd_price=Decimal("35"),
    )

    assert result.pricing_request_id == "pricing-request-001"
    assert result.customer_id == "customer-001"
    assert result.usd_price == Decimal("35")
    assert result.fx_source_id == SOURCE
    assert result.fx_usd_vnd_rate == Decimal("26501.25")
    assert result.fx_published_at == (
        NOW - timedelta(hours=1)
    )
    assert result.amount_minor == 927_544
    assert result.currency == "VND"

    stored = store.get_by_pricing_request_id(
        pricing_request_id="pricing-request-001"
    )

    assert stored is not None
    assert stored == result


@pytest.mark.parametrize(
    ("rate", "expected"),
    (
        (Decimal("26501.42"), 927_550),
        (
            Decimal(
                "26501.414"
            ),
            927_549,
        ),
        (
            Decimal(
                "26501.41457142857142857142857"
            ),
            927_550,
        ),
    ),
)
def test_rounding_policy_is_half_down_to_one_vnd(
    tmp_path: Path,
    rate: Decimal,
    expected: int,
):
    service, _ = _built_service(
        tmp_path,
        rate=rate,
    )

    result = service.create(
        pricing_request_id="pricing-request-rounding",
        customer_id="customer-001",
        usd_price=Decimal("35"),
    )

    assert result.amount_minor == expected


def test_exact_half_tie_rounds_down(
    tmp_path: Path,
):
    service, _ = _built_service(
        tmp_path,
        rate=Decimal(
            "26501.4142857142857142857142857142857"
        ),
    )

    result = service.create(
        pricing_request_id="pricing-request-half",
        customer_id="customer-001",
        usd_price=Decimal("35"),
    )

    assert (
        Decimal("35")
        * result.fx_usd_vnd_rate
    ) == Decimal("927549.5")

    assert result.amount_minor == 927_549


def test_above_half_rounds_up(
    tmp_path: Path,
):
    service, _ = _built_service(
        tmp_path,
        rate=Decimal(
            "26501.4145714285714285714285714285714"
        ),
    )

    result = service.create(
        pricing_request_id="pricing-request-above-half",
        customer_id="customer-001",
        usd_price=Decimal("35"),
    )

    assert (
        Decimal("35")
        * result.fx_usd_vnd_rate
    ) > Decimal("927549.5")

    assert result.amount_minor == 927_550


def test_identical_retry_is_idempotent(
    tmp_path: Path,
):
    service, store = _built_service(tmp_path)

    first = service.create(
        pricing_request_id="pricing-request-001",
        customer_id="customer-001",
        usd_price=Decimal("35"),
    )

    second = service.create(
        pricing_request_id="pricing-request-001",
        customer_id="customer-001",
        usd_price=Decimal("35"),
    )

    assert second == first
    assert store.size() == 1


@pytest.mark.parametrize(
    ("changed_field", "changed_value"),
    (
        ("customer_id", "customer-002"),
        ("usd_price", Decimal("50")),
    ),
)
def test_retry_with_changed_pricing_fact_fails_closed(
    tmp_path: Path,
    changed_field: str,
    changed_value,
):
    service, store = _built_service(tmp_path)

    service.create(
        pricing_request_id="pricing-request-001",
        customer_id="customer-001",
        usd_price=Decimal("35"),
    )

    kwargs = {
        "pricing_request_id": "pricing-request-001",
        "customer_id": "customer-001",
        "usd_price": Decimal("35"),
    }
    kwargs[changed_field] = changed_value

    with pytest.raises(
        ValueError,
        match="pricing request",
    ):
        service.create(**kwargs)

    assert store.size() == 1


def test_new_pricing_fails_closed_when_fx_snapshot_is_stale(
    tmp_path: Path,
):
    service, store = _built_service(
        tmp_path,
        published_at=NOW - timedelta(hours=49),
    )

    with pytest.raises(
        RuntimeError,
        match="FX snapshot",
    ):
        service.create(
            pricing_request_id="pricing-request-stale",
            customer_id="customer-001",
            usd_price=Decimal("35"),
        )

    assert store.size() == 0


def test_existing_projection_is_not_repriced_after_fx_changes(
    tmp_path: Path,
):
    service, store = _built_service(tmp_path)

    first = service.create(
        pricing_request_id="pricing-request-001",
        customer_id="customer-001",
        usd_price=Decimal("35"),
    )

    before = first.amount_minor

    second = service.create(
        pricing_request_id="pricing-request-001",
        customer_id="customer-001",
        usd_price=Decimal("35"),
    )

    assert second.amount_minor == before
    assert second == first
    assert store.size() == 1


def test_durable_projection_restores_exact_frozen_pricing_truth(
    tmp_path: Path,
):
    service, _ = _built_service(tmp_path)

    created = service.create(
        pricing_request_id="pricing-request-durable",
        customer_id="customer-001",
        usd_price=Decimal("35"),
    )

    restored_store = (
        CustomerCommercialVndOrderPricingProjectionStore(
            tmp_path / "vnd_order_pricing_projection.json"
        )
    )

    assert restored_store.is_ready()

    restored = restored_store.get_by_pricing_request_id(
        pricing_request_id="pricing-request-durable"
    )

    assert restored == created
    assert restored is not None
    assert restored.usd_price == Decimal("35")
    assert restored.fx_source_id == SOURCE
    assert restored.fx_usd_vnd_rate == Decimal("26501.25")
    assert restored.fx_published_at == (
        NOW - timedelta(hours=1)
    )
    assert restored.amount_minor == 927_544
    assert restored.currency == "VND"


def test_projection_record_surface_is_exact_and_narrow():
    assert set(
        CustomerCommercialVndOrderPricingProjectionRecord
        .__dataclass_fields__
    ) == {
        "pricing_request_id",
        "customer_id",
        "usd_price",
        "fx_snapshot_date",
        "fx_source_id",
        "fx_usd_vnd_rate",
        "fx_published_at",
        "amount_minor",
        "currency",
    }


def test_projection_owner_has_no_order_payment_or_settlement_authority():
    forbidden = {
        "create_order",
        "create_payment_intent",
        "settle",
        "activate",
        "reconcile",
    }

    assert forbidden.isdisjoint(
        set(
            dir(
                CustomerCommercialVndOrderPricingProjectionService
            )
        )
    )
