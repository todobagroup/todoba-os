"""
P9B3 ? Daily Authoritative FX Refresh Composition.

P9B2 provider result
    -> P9B1 durable snapshot

Scheduler owns timing only.

No freshness TTL, stale policy, order pricing,
payment, settlement or entitlement authority.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.commercial.customer_commercial_fx_snapshot_service import (
    CustomerCommercialFXSnapshotStore,
)
from backend.commercial.customer_commercial_vietcombank_fx_adapter import (
    VIETCOMBANK_FX_SOURCE_ID,
    VIETNAM_TIMEZONE,
    VietcombankFXAdapter,
    VietcombankFXResult,
)
from backend.commercial.customer_commercial_fx_daily_refresh_service import (
    CustomerCommercialFXDailyRefreshScheduler,
    CustomerCommercialFXDailyRefreshService,
)


PUBLISHED_AT = datetime(
    2026,
    9,
    17,
    7,
    0,
    tzinfo=VIETNAM_TIMEZONE,
).astimezone(
    UTC
)

FETCHED_AT = datetime(
    2026,
    9,
    17,
    0,
    0,
    5,
    tzinfo=UTC,
)


class FakeAdapter(VietcombankFXAdapter):
    def __init__(
        self,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.fetch_count = 0

    def fetch(self):
        self.fetch_count += 1

        if self.error is not None:
            raise self.error

        return self.result


def provider_result(
    *,
    rate=Decimal("26500"),
    published_at=PUBLISHED_AT,
    fetched_at=FETCHED_AT,
):
    return VietcombankFXResult(
        source_id=VIETCOMBANK_FX_SOURCE_ID,
        base_currency="USD",
        quote_currency="VND",
        usd_vnd_rate=rate,
        published_at=published_at,
        fetched_at=fetched_at,
    )


def ready_store(tmp_path):
    store = CustomerCommercialFXSnapshotStore(
        tmp_path / "fx.json"
    )
    store.initialize_empty()
    return store


def service(
    tmp_path,
    *,
    result=None,
    error=None,
):
    store = ready_store(tmp_path)

    adapter = FakeAdapter(
        result=(
            provider_result()
            if result is None
            else result
        ),
        error=error,
    )

    instance = CustomerCommercialFXDailyRefreshService(
        adapter=adapter,
        snapshot_store=store,
    )

    return instance, adapter, store


def test_refresh_publishes_provider_result(
    tmp_path,
):
    instance, adapter, store = service(
        tmp_path
    )

    snapshot = instance.refresh_once()

    assert adapter.fetch_count == 1

    assert snapshot.snapshot_date.isoformat() == (
        "2026-09-17"
    )

    assert snapshot.source_id == (
        VIETCOMBANK_FX_SOURCE_ID
    )

    assert snapshot.base_currency == "USD"
    assert snapshot.quote_currency == "VND"
    assert snapshot.usd_vnd_rate == Decimal(
        "26500"
    )

    assert snapshot.published_at == PUBLISHED_AT
    assert snapshot.fetched_at == FETCHED_AT

    restored = store.get(
        snapshot_date=snapshot.snapshot_date,
        source_id=snapshot.source_id,
        base_currency="USD",
        quote_currency="VND",
    )

    assert restored == snapshot


def test_snapshot_date_comes_from_provider_vietnam_date(
    tmp_path,
):
    provider_time = datetime(
        2026,
        9,
        17,
        23,
        30,
        tzinfo=VIETNAM_TIMEZONE,
    ).astimezone(
        UTC
    )

    result = provider_result(
        published_at=provider_time
    )

    instance, _, _ = service(
        tmp_path,
        result=result,
    )

    snapshot = instance.refresh_once()

    assert snapshot.snapshot_date.isoformat() == (
        "2026-09-17"
    )


def test_fetch_failure_does_not_mutate_store(
    tmp_path,
):
    instance, _, store = service(
        tmp_path,
        error=RuntimeError(
            "provider unavailable"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="provider unavailable",
    ):
        instance.refresh_once()

    assert store.get(
        snapshot_date=datetime(
            2026,
            9,
            17,
            tzinfo=UTC,
        ).date(),
        source_id=VIETCOMBANK_FX_SOURCE_ID,
        base_currency="USD",
        quote_currency="VND",
    ) is None


def test_same_authoritative_provider_facts_converge(
    tmp_path,
):
    instance, adapter, store = service(
        tmp_path
    )

    first = instance.refresh_once()

    adapter.result = provider_result(
        fetched_at=datetime(
            2026,
            9,
            17,
            0,
            5,
            tzinfo=UTC,
        )
    )

    second = instance.refresh_once()

    assert adapter.fetch_count == 2
    assert second == first

    stored = store.get(
        snapshot_date=first.snapshot_date,
        source_id=first.source_id,
        base_currency="USD",
        quote_currency="VND",
    )

    assert stored == first


def test_same_identity_changed_rate_fails_closed(
    tmp_path,
):
    instance, adapter, _ = service(
        tmp_path
    )

    instance.refresh_once()

    adapter.result = provider_result(
        rate=Decimal("26501"),
        fetched_at=datetime(
            2026,
            9,
            17,
            0,
            5,
            tzinfo=UTC,
        ),
    )

    with pytest.raises(
        ValueError,
        match="different",
    ):
        instance.refresh_once()


def test_same_identity_changed_published_at_fails_closed(
    tmp_path,
):
    instance, adapter, _ = service(
        tmp_path
    )

    instance.refresh_once()

    adapter.result = provider_result(
        published_at=datetime(
            2026,
            9,
            17,
            8,
            0,
            tzinfo=VIETNAM_TIMEZONE,
        ).astimezone(
            UTC
        ),
        fetched_at=datetime(
            2026,
            9,
            17,
            1,
            0,
            tzinfo=UTC,
        ),
    )

    with pytest.raises(
        ValueError,
        match="different",
    ):
        instance.refresh_once()


def test_service_requires_ready_snapshot_store(
    tmp_path,
):
    store = CustomerCommercialFXSnapshotStore(
        tmp_path / "not-ready.json"
    )

    adapter = FakeAdapter(
        result=provider_result()
    )

    with pytest.raises(
        RuntimeError,
        match="initialized",
    ):
        CustomerCommercialFXDailyRefreshService(
            adapter=adapter,
            snapshot_store=store,
        )


def test_next_run_before_0700_is_today():
    now = datetime(
        2026,
        9,
        17,
        6,
        30,
        tzinfo=VIETNAM_TIMEZONE,
    )

    next_run = (
        CustomerCommercialFXDailyRefreshScheduler
        .next_run_at(
            now
        )
    )

    assert next_run == datetime(
        2026,
        9,
        17,
        7,
        0,
        tzinfo=VIETNAM_TIMEZONE,
    )


def test_next_run_at_0700_is_next_day():
    now = datetime(
        2026,
        9,
        17,
        7,
        0,
        tzinfo=VIETNAM_TIMEZONE,
    )

    next_run = (
        CustomerCommercialFXDailyRefreshScheduler
        .next_run_at(
            now
        )
    )

    assert next_run == datetime(
        2026,
        9,
        18,
        7,
        0,
        tzinfo=VIETNAM_TIMEZONE,
    )


def test_next_run_after_0700_is_next_day():
    now = datetime(
        2026,
        9,
        17,
        10,
        0,
        tzinfo=VIETNAM_TIMEZONE,
    )

    next_run = (
        CustomerCommercialFXDailyRefreshScheduler
        .next_run_at(
            now
        )
    )

    assert next_run == datetime(
        2026,
        9,
        18,
        7,
        0,
        tzinfo=VIETNAM_TIMEZONE,
    )


def test_scheduler_run_cycle_calls_refresh_service(
    tmp_path,
):
    instance, adapter, _ = service(
        tmp_path
    )

    scheduler = CustomerCommercialFXDailyRefreshScheduler(
        refresh_service=instance,
        clock=lambda: datetime(
            2026,
            9,
            17,
            7,
            0,
            tzinfo=VIETNAM_TIMEZONE,
        ),
    )

    cycle = scheduler.run_cycle()

    assert adapter.fetch_count == 1
    assert cycle.cycle_number == 1
    assert cycle.snapshot is not None


def test_scheduler_owns_no_pricing_or_freshness_authority(
    tmp_path,
):
    instance, _, _ = service(
        tmp_path
    )

    scheduler = CustomerCommercialFXDailyRefreshScheduler(
        refresh_service=instance,
        clock=lambda: datetime(
            2026,
            9,
            17,
            7,
            0,
            tzinfo=VIETNAM_TIMEZONE,
        ),
    )

    for forbidden in (
        "freshness_ttl",
        "stale",
        "amount_vnd",
        "amount_due",
        "order_id",
        "payment_intent_id",
        "settlement_id",
        "entitlement_id",
    ):
        assert not hasattr(
            scheduler,
            forbidden,
        )
