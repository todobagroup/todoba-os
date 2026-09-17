"""
P9B1A ? Authoritative Latest FX Snapshot Read Surface.

Adds only a public read operation to the existing
authoritative FX snapshot store.

No freshness, scheduling, pricing, payment, or mutation
authority is introduced by this capability.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from backend.commercial.customer_commercial_fx_snapshot_service import (
    CustomerCommercialFXSnapshotRecord,
    CustomerCommercialFXSnapshotStore,
)


SOURCE = "vietcombank-official"


def snapshot(
    *,
    snapshot_date: date,
    source_id: str = SOURCE,
    rate: str = "26500",
):
    published_at = datetime(
        snapshot_date.year,
        snapshot_date.month,
        snapshot_date.day,
        0,
        0,
        tzinfo=UTC,
    )

    return CustomerCommercialFXSnapshotRecord(
        snapshot_date=snapshot_date,
        source_id=source_id,
        base_currency="USD",
        quote_currency="VND",
        usd_vnd_rate=Decimal(rate),
        published_at=published_at,
        fetched_at=published_at,
    )


def ready_store(tmp_path):
    store = CustomerCommercialFXSnapshotStore(
        tmp_path / "fx.json"
    )
    store.initialize_empty()
    return store


def test_latest_returns_none_when_no_snapshot_exists(
    tmp_path,
):
    store = ready_store(tmp_path)

    assert store.latest(
        source_id=SOURCE,
        base_currency="USD",
        quote_currency="VND",
    ) is None


def test_latest_returns_greatest_snapshot_date(
    tmp_path,
):
    store = ready_store(tmp_path)

    older = store.save(
        snapshot(
            snapshot_date=date(
                2026,
                9,
                16,
            ),
            rate="26400",
        )
    )

    newest = store.save(
        snapshot(
            snapshot_date=date(
                2026,
                9,
                17,
            ),
            rate="26500",
        )
    )

    assert older != newest

    assert store.latest(
        source_id=SOURCE,
        base_currency="USD",
        quote_currency="VND",
    ) == newest


def test_latest_is_source_specific(
    tmp_path,
):
    store = ready_store(tmp_path)

    expected = store.save(
        snapshot(
            snapshot_date=date(
                2026,
                9,
                16,
            ),
            source_id=SOURCE,
            rate="26400",
        )
    )

    store.save(
        snapshot(
            snapshot_date=date(
                2026,
                9,
                17,
            ),
            source_id="secondary-source",
            rate="26550",
        )
    )

    assert store.latest(
        source_id=SOURCE,
        base_currency="USD",
        quote_currency="VND",
    ) == expected


def test_latest_survives_durable_reload(
    tmp_path,
):
    path = tmp_path / "fx.json"

    first = CustomerCommercialFXSnapshotStore(
        path
    )
    first.initialize_empty()

    expected = first.save(
        snapshot(
            snapshot_date=date(
                2026,
                9,
                17,
            )
        )
    )

    restored = CustomerCommercialFXSnapshotStore(
        path
    )
    restored.load()

    assert restored.latest(
        source_id=SOURCE,
        base_currency="USD",
        quote_currency="VND",
    ) == expected


def test_latest_requires_initialized_store(
    tmp_path,
):
    store = CustomerCommercialFXSnapshotStore(
        tmp_path / "not-ready.json"
    )

    with pytest.raises(
        RuntimeError,
        match="initialized",
    ):
        store.latest(
            source_id=SOURCE,
            base_currency="USD",
            quote_currency="VND",
        )


@pytest.mark.parametrize(
    (
        "base_currency",
        "quote_currency",
    ),
    [
        ("EUR", "VND"),
        ("USD", "EUR"),
    ],
)
def test_latest_rejects_non_usd_vnd_pair(
    tmp_path,
    base_currency,
    quote_currency,
):
    store = ready_store(tmp_path)

    with pytest.raises(
        ValueError,
        match="USD/VND",
    ):
        store.latest(
            source_id=SOURCE,
            base_currency=base_currency,
            quote_currency=quote_currency,
        )


def test_latest_is_read_only_surface():
    forbidden = (
        "freshness_ttl",
        "max_age",
        "stale",
        "amount_vnd",
        "amount_due",
        "order_id",
        "payment_intent_id",
        "settlement_id",
        "entitlement_id",
    )

    for name in forbidden:
        assert not hasattr(
            CustomerCommercialFXSnapshotStore,
            name,
        )
