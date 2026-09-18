from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.commercial.customer_commercial_billing_cycle_baseline_service import (
    CustomerCommercialBillingCycleBaselineRecord,
    CustomerCommercialBillingCycleBaselineStore,
)
from backend.commercial.customer_commercial_current_billing_cycle_service import (
    CustomerCommercialCurrentBillingCycleService,
    CustomerCommercialCurrentBillingCycleStore,
)


def _baseline(
    *,
    cycle_id: str,
    customer_id: str,
    started_at: datetime,
) -> CustomerCommercialBillingCycleBaselineRecord:
    return CustomerCommercialBillingCycleBaselineRecord(
        cycle_id=cycle_id,
        customer_id=customer_id,
        cycle_started_at=started_at,
        authoritative_cycle_balance_usd=Decimal("1000"),
        licensed_account_cap_usd=1000,
        standard_monthly_price_usd=50,
    )


def _build(tmp_path):
    baseline_store = CustomerCommercialBillingCycleBaselineStore(
        tmp_path / "baselines.json"
    )
    baseline_store.initialize_empty()

    current_store = CustomerCommercialCurrentBillingCycleStore(
        tmp_path / "current-cycle.json"
    )
    current_store.initialize_empty()

    service = CustomerCommercialCurrentBillingCycleService(
        store=current_store,
        billing_cycle_store=baseline_store,
    )

    return (
        baseline_store,
        current_store,
        service,
    )


def test_set_and_resolve_authoritative_current_cycle(
    tmp_path,
) -> None:
    (
        baseline_store,
        _,
        service,
    ) = _build(tmp_path)

    baseline = _baseline(
        cycle_id="cycle-001",
        customer_id="customer-001",
        started_at=datetime(
            2026,
            9,
            1,
            tzinfo=UTC,
        ),
    )

    baseline_store.save(baseline)

    service.set_current(
        customer_id="customer-001",
        cycle_id="cycle-001",
    )

    assert (
        service.resolve_current(
            customer_id="customer-001"
        )
        == baseline
    )


def test_current_cycle_can_advance_without_mutating_old_baseline(
    tmp_path,
) -> None:
    (
        baseline_store,
        _,
        service,
    ) = _build(tmp_path)

    first = _baseline(
        cycle_id="cycle-001",
        customer_id="customer-001",
        started_at=datetime(
            2026,
            9,
            1,
            tzinfo=UTC,
        ),
    )

    second = _baseline(
        cycle_id="cycle-002",
        customer_id="customer-001",
        started_at=datetime(
            2026,
            10,
            1,
            tzinfo=UTC,
        ),
    )

    baseline_store.save(first)
    baseline_store.save(second)

    service.set_current(
        customer_id="customer-001",
        cycle_id="cycle-001",
    )

    service.set_current(
        customer_id="customer-001",
        cycle_id="cycle-002",
    )

    assert (
        service.resolve_current(
            customer_id="customer-001"
        )
        == second
    )

    assert (
        baseline_store.get(
            cycle_id="cycle-001"
        )
        == first
    )


def test_unknown_cycle_fails_closed(
    tmp_path,
) -> None:
    _, _, service = _build(tmp_path)

    with pytest.raises(
        RuntimeError,
        match="billing cycle",
    ):
        service.set_current(
            customer_id="customer-001",
            cycle_id="missing-cycle",
        )


def test_foreign_customer_cycle_fails_closed(
    tmp_path,
) -> None:
    (
        baseline_store,
        _,
        service,
    ) = _build(tmp_path)

    baseline_store.save(
        _baseline(
            cycle_id="cycle-001",
            customer_id="customer-001",
            started_at=datetime(
                2026,
                9,
                1,
                tzinfo=UTC,
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
        match="customer",
    ):
        service.set_current(
            customer_id="customer-002",
            cycle_id="cycle-001",
        )


def test_missing_current_cycle_fails_closed(
    tmp_path,
) -> None:
    _, _, service = _build(tmp_path)

    with pytest.raises(
        RuntimeError,
        match="current billing cycle",
    ):
        service.resolve_current(
            customer_id="customer-001"
        )


def test_service_does_not_infer_latest_baseline_as_current(
    tmp_path,
) -> None:
    (
        baseline_store,
        _,
        service,
    ) = _build(tmp_path)

    baseline_store.save(
        _baseline(
            cycle_id="cycle-old",
            customer_id="customer-001",
            started_at=datetime(
                2026,
                8,
                1,
                tzinfo=UTC,
            ),
        )
    )

    baseline_store.save(
        _baseline(
            cycle_id="cycle-newer",
            customer_id="customer-001",
            started_at=datetime(
                2026,
                9,
                1,
                tzinfo=UTC,
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
        match="current billing cycle",
    ):
        service.resolve_current(
            customer_id="customer-001"
        )


def test_current_cycle_store_is_durable(
    tmp_path,
) -> None:
    baseline_path = tmp_path / "baselines.json"
    current_path = tmp_path / "current-cycle.json"

    baseline_store = CustomerCommercialBillingCycleBaselineStore(
        baseline_path
    )
    baseline_store.initialize_empty()

    baseline = _baseline(
        cycle_id="cycle-001",
        customer_id="customer-001",
        started_at=datetime(
            2026,
            9,
            1,
            tzinfo=UTC,
        ),
    )
    baseline_store.save(baseline)

    current_store = CustomerCommercialCurrentBillingCycleStore(
        current_path
    )
    current_store.initialize_empty()

    service = CustomerCommercialCurrentBillingCycleService(
        store=current_store,
        billing_cycle_store=baseline_store,
    )

    service.set_current(
        customer_id="customer-001",
        cycle_id="cycle-001",
    )

    restored_current_store = (
        CustomerCommercialCurrentBillingCycleStore(
            current_path
        )
    )
    restored_current_store.load()

    restored_baseline_store = (
        CustomerCommercialBillingCycleBaselineStore(
            baseline_path
        )
    )
    restored_baseline_store.load()

    restored_service = (
        CustomerCommercialCurrentBillingCycleService(
            store=restored_current_store,
            billing_cycle_store=restored_baseline_store,
        )
    )

    assert (
        restored_service.resolve_current(
            customer_id="customer-001"
        )
        == baseline
    )
