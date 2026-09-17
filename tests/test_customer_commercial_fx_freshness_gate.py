"""
P9B4 ? Last-Known-Good FX Freshness Gate.

Consumes the authoritative latest FX snapshot and decides
whether it is currently usable.

Freshness is measured from authoritative published_at,
never from fetched_at.

Production max-age policy is injected; this capability does
not hardcode a commercial TTL.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from backend.commercial.customer_commercial_fx_snapshot_service import (
    CustomerCommercialFXSnapshotRecord,
    CustomerCommercialFXSnapshotStore,
)
from backend.commercial.customer_commercial_fx_freshness_gate import (
    CustomerCommercialFXFreshnessGate,
    CustomerCommercialFXFreshnessResult,
)


SOURCE = "vietcombank-official"

NOW = datetime(
    2026,
    9,
    17,
    12,
    0,
    tzinfo=UTC,
)

MAX_AGE = timedelta(
    hours=48,
)


def snapshot(
    *,
    published_at: datetime,
    fetched_at: datetime | None = None,
    rate: str = "26500",
):
    if fetched_at is None:
        fetched_at = published_at

    return CustomerCommercialFXSnapshotRecord(
        snapshot_date=published_at.date(),
        source_id=SOURCE,
        base_currency="USD",
        quote_currency="VND",
        usd_vnd_rate=Decimal(rate),
        published_at=published_at,
        fetched_at=fetched_at,
    )


def ready_store(tmp_path):
    store = CustomerCommercialFXSnapshotStore(
        tmp_path / "fx.json"
    )
    store.initialize_empty()
    return store


def gate(
    tmp_path,
    *,
    now=NOW,
    max_age=MAX_AGE,
):
    store = ready_store(tmp_path)

    instance = CustomerCommercialFXFreshnessGate(
        snapshot_store=store,
        source_id=SOURCE,
        max_age=max_age,
        clock=lambda: now,
    )

    return instance, store


def test_no_snapshot_is_unavailable(
    tmp_path,
):
    instance, _ = gate(tmp_path)

    result = instance.evaluate()

    assert isinstance(
        result,
        CustomerCommercialFXFreshnessResult,
    )

    assert result.status == "unavailable"
    assert result.snapshot is None
    assert result.age is None


def test_fresh_latest_snapshot_is_usable(
    tmp_path,
):
    instance, store = gate(tmp_path)

    expected = store.save(
        snapshot(
            published_at=(
                NOW
                - timedelta(
                    hours=2
                )
            )
        )
    )

    result = instance.evaluate()

    assert result.status == "usable"
    assert result.snapshot == expected
    assert result.age == timedelta(
        hours=2
    )


def test_exact_max_age_is_still_usable(
    tmp_path,
):
    instance, store = gate(tmp_path)

    expected = store.save(
        snapshot(
            published_at=(
                NOW
                - MAX_AGE
            )
        )
    )

    result = instance.evaluate()

    assert result.status == "usable"
    assert result.snapshot == expected
    assert result.age == MAX_AGE


def test_older_than_max_age_is_stale(
    tmp_path,
):
    instance, store = gate(tmp_path)

    expected = store.save(
        snapshot(
            published_at=(
                NOW
                - MAX_AGE
                - timedelta(
                    seconds=1
                )
            )
        )
    )

    result = instance.evaluate()

    assert result.status == "stale"
    assert result.snapshot == expected
    assert result.age == (
        MAX_AGE
        + timedelta(
            seconds=1
        )
    )


def test_future_published_snapshot_fails_closed_as_stale(
    tmp_path,
):
    instance, store = gate(tmp_path)

    expected = store.save(
        snapshot(
            published_at=(
                NOW
                + timedelta(
                    seconds=1
                )
            )
        )
    )

    result = instance.evaluate()

    assert result.status == "stale"
    assert result.snapshot == expected
    assert result.age == timedelta(
        seconds=-1
    )


def test_freshness_uses_published_at_not_fetched_at(
    tmp_path,
):
    instance, store = gate(tmp_path)

    old_publication = (
        NOW
        - MAX_AGE
        - timedelta(
            hours=1
        )
    )

    freshly_fetched = (
        NOW
        - timedelta(
            seconds=5
        )
    )

    store.save(
        snapshot(
            published_at=old_publication,
            fetched_at=freshly_fetched,
        )
    )

    result = instance.evaluate()

    assert result.status == "stale"
    assert result.age == (
        NOW
        - old_publication
    )


def test_latest_snapshot_is_selected(
    tmp_path,
):
    instance, store = gate(tmp_path)

    store.save(
        snapshot(
            published_at=(
                NOW
                - timedelta(
                    days=2
                )
            ),
            rate="26400",
        )
    )

    newest = store.save(
        snapshot(
            published_at=(
                NOW
                - timedelta(
                    hours=1
                )
            ),
            rate="26500",
        )
    )

    result = instance.evaluate()

    assert result.status == "usable"
    assert result.snapshot == newest


def test_require_usable_returns_authoritative_snapshot(
    tmp_path,
):
    instance, store = gate(tmp_path)

    expected = store.save(
        snapshot(
            published_at=(
                NOW
                - timedelta(
                    hours=1
                )
            )
        )
    )

    assert (
        instance.require_usable()
        == expected
    )


@pytest.mark.parametrize(
    "published_delta",
    [
        timedelta(
            hours=-49
        ),
        timedelta(
            seconds=1
        ),
    ],
)
def test_require_usable_fails_closed_for_unusable_snapshot(
    tmp_path,
    published_delta,
):
    instance, store = gate(tmp_path)

    store.save(
        snapshot(
            published_at=(
                NOW
                + published_delta
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match="FX snapshot",
    ):
        instance.require_usable()


def test_require_usable_fails_closed_when_unavailable(
    tmp_path,
):
    instance, _ = gate(tmp_path)

    with pytest.raises(
        RuntimeError,
        match="FX snapshot",
    ):
        instance.require_usable()


@pytest.mark.parametrize(
    "max_age",
    [
        timedelta(0),
        timedelta(
            seconds=-1
        ),
        "48h",
        48,
    ],
)
def test_max_age_must_be_positive_timedelta(
    tmp_path,
    max_age,
):
    store = ready_store(tmp_path)

    with pytest.raises(
        (TypeError, ValueError),
    ):
        CustomerCommercialFXFreshnessGate(
            snapshot_store=store,
            source_id=SOURCE,
            max_age=max_age,
            clock=lambda: NOW,
        )


def test_clock_must_return_timezone_aware_datetime(
    tmp_path,
):
    store = ready_store(tmp_path)

    store.save(
        snapshot(
            published_at=(
                NOW
                - timedelta(
                    hours=1
                )
            )
        )
    )

    instance = CustomerCommercialFXFreshnessGate(
        snapshot_store=store,
        source_id=SOURCE,
        max_age=MAX_AGE,
        clock=lambda: datetime(
            2026,
            9,
            17,
            12,
            0,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="timezone-aware",
    ):
        instance.evaluate()


def test_result_shape_is_narrow():
    assert set(
        CustomerCommercialFXFreshnessResult
        .__dataclass_fields__
    ) == {
        "status",
        "snapshot",
        "age",
    }


def test_gate_has_no_downstream_authority():
    forbidden = (
        "amount_vnd",
        "amount_due",
        "order_id",
        "payment_intent_id",
        "settlement_id",
        "entitlement_id",
        "refresh",
        "fetch",
    )

    for name in forbidden:
        assert not hasattr(
            CustomerCommercialFXFreshnessGate,
            name,
        )
