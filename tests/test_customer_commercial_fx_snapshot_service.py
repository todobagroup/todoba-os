"""
P9B1 ? Authoritative FX Snapshot Authority.

Provider-neutral durable publication of one exact
USD/VND source snapshot.

This capability does NOT:
- fetch network FX data
- choose HTTP endpoints
- schedule refreshes
- define freshness TTL
- price or mutate commercial orders
- verify payments
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from backend.commercial.customer_commercial_fx_snapshot_service import (
    CustomerCommercialFXSnapshotRecord,
    CustomerCommercialFXSnapshotStore,
)


SOURCE = "vietcombank-official"
SNAPSHOT_DATE = date(2026, 9, 17)
PUBLISHED_AT = datetime(
    2026,
    9,
    17,
    7,
    0,
    tzinfo=UTC,
)
FETCHED_AT = datetime(
    2026,
    9,
    17,
    7,
    0,
    5,
    tzinfo=UTC,
)


def record(
    *,
    snapshot_date=SNAPSHOT_DATE,
    source_id=SOURCE,
    rate=Decimal("26500"),
    published_at=PUBLISHED_AT,
    fetched_at=FETCHED_AT,
):
    return CustomerCommercialFXSnapshotRecord(
        snapshot_date=snapshot_date,
        source_id=source_id,
        base_currency="USD",
        quote_currency="VND",
        usd_vnd_rate=rate,
        published_at=published_at,
        fetched_at=fetched_at,
    )


def ready_store(tmp_path):
    store = CustomerCommercialFXSnapshotStore(
        tmp_path / "commercial-fx-snapshots.json"
    )
    store.initialize_empty()
    return store


def test_snapshot_is_durably_saved(tmp_path):
    store = ready_store(tmp_path)

    saved = store.save(
        record()
    )

    assert saved.snapshot_date == SNAPSHOT_DATE
    assert saved.source_id == SOURCE
    assert saved.base_currency == "USD"
    assert saved.quote_currency == "VND"
    assert saved.usd_vnd_rate == Decimal("26500")
    assert saved.published_at == PUBLISHED_AT
    assert saved.fetched_at == FETCHED_AT


def test_exact_retry_is_idempotent(tmp_path):
    store = ready_store(tmp_path)

    first = store.save(record())
    second = store.save(record())

    assert second == first


def test_same_identity_cannot_change_rate(tmp_path):
    store = ready_store(tmp_path)

    store.save(record())

    with pytest.raises(
        ValueError,
        match="different",
    ):
        store.save(
            record(
                rate=Decimal("26501")
            )
        )


def test_same_identity_cannot_change_published_at(
    tmp_path,
):
    store = ready_store(tmp_path)

    store.save(record())

    with pytest.raises(
        ValueError,
        match="different",
    ):
        store.save(
            record(
                published_at=datetime(
                    2026,
                    9,
                    17,
                    7,
                    1,
                    tzinfo=UTC,
                )
            )
        )


def test_identity_is_date_source_and_currency_pair(
    tmp_path,
):
    store = ready_store(tmp_path)

    first = store.save(record())

    other_source = store.save(
        record(
            source_id="secondary-source"
        )
    )

    assert first != other_source


def test_only_usd_vnd_pair_is_allowed():
    with pytest.raises(
        ValueError,
        match="USD/VND",
    ):
        CustomerCommercialFXSnapshotRecord(
            snapshot_date=SNAPSHOT_DATE,
            source_id=SOURCE,
            base_currency="EUR",
            quote_currency="VND",
            usd_vnd_rate=Decimal("26500"),
            published_at=PUBLISHED_AT,
            fetched_at=FETCHED_AT,
        )


@pytest.mark.parametrize(
    "rate",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
    ],
)
def test_rate_must_be_positive_finite(rate):
    with pytest.raises(ValueError):
        record(
            rate=rate
        )


def test_snapshot_survives_restart(tmp_path):
    path = tmp_path / "commercial-fx-snapshots.json"

    first_store = CustomerCommercialFXSnapshotStore(
        path
    )
    first_store.initialize_empty()

    expected = first_store.save(
        record()
    )

    restored = CustomerCommercialFXSnapshotStore(
        path
    )
    restored.load()

    actual = restored.get(
        snapshot_date=SNAPSHOT_DATE,
        source_id=SOURCE,
        base_currency="USD",
        quote_currency="VND",
    )

    assert actual == expected


def test_missing_store_load_fails_closed(tmp_path):
    store = CustomerCommercialFXSnapshotStore(
        tmp_path / "missing.json"
    )

    with pytest.raises(
        RuntimeError,
        match="does not exist",
    ):
        store.load()


def test_existing_store_cannot_be_reinitialized(
    tmp_path,
):
    path = tmp_path / "commercial-fx-snapshots.json"

    first = CustomerCommercialFXSnapshotStore(
        path
    )
    first.initialize_empty()

    second = CustomerCommercialFXSnapshotStore(
        path
    )

    with pytest.raises(
        RuntimeError,
        match="already exists",
    ):
        second.initialize_empty()


def test_uninitialized_store_fails_closed(tmp_path):
    store = CustomerCommercialFXSnapshotStore(
        tmp_path / "not-ready.json"
    )

    with pytest.raises(
        RuntimeError,
        match="initialized",
    ):
        store.save(
            record()
        )


def test_snapshot_owner_has_no_downstream_authority():
    record_fields = {
        field
        for field in (
            CustomerCommercialFXSnapshotRecord
            .__dataclass_fields__
        )
    }

    for forbidden in (
        "amount_vnd",
        "amount_due",
        "order_id",
        "payment_intent_id",
        "settlement_id",
        "entitlement_id",
        "freshness_ttl",
        "stale",
        "upgrade_required",
    ):
        assert forbidden not in record_fields
