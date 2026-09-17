"""
P9A3 ? Commercial Billing Cycle Baseline Authority.

Proof:

authoritative cycle-start / renewal balance
->
P9A2 USD Price Book
->
immutable durable billing-cycle baseline

The baseline freezes commercial truth for one cycle.

Later live trading profit/loss must not mutate it.

This capability does not own:
- live balance observation
- deposit / withdrawal classification
- grace
- upgrade enforcement
- renewal scheduling
- payment
- settlement
- entitlement
- runtime trading authority
"""

from datetime import UTC
from datetime import datetime
from decimal import Decimal

import pytest

from backend.commercial.customer_commercial_billing_cycle_baseline_service import (
    CustomerCommercialBillingCycleBaselineRecord,
    CustomerCommercialBillingCycleBaselineService,
    CustomerCommercialBillingCycleBaselineStore,
)
from backend.commercial.customer_commercial_account_price_book import (
    CustomerCommercialAccountPriceBook,
)


CUSTOMER_ID = "customer-p9a3-001"
CYCLE_ID = "billing-cycle-p9a3-001"

STARTED_AT = datetime(
    2026,
    9,
    17,
    0,
    0,
    tzinfo=UTC,
)


def build_service(
    tmp_path,
):
    store = CustomerCommercialBillingCycleBaselineStore(
        tmp_path / "commercial_billing_cycles.json"
    )

    store.initialize_empty()

    service = CustomerCommercialBillingCycleBaselineService(
        store=store,
        price_book=CustomerCommercialAccountPriceBook,
    )

    return service, store


def create_baseline(
    service,
    *,
    cycle_id: str = CYCLE_ID,
    customer_id: str = CUSTOMER_ID,
    cycle_started_at: datetime = STARTED_AT,
    balance: str = "1000.00",
):
    return service.create(
        cycle_id=cycle_id,
        customer_id=customer_id,
        cycle_started_at=cycle_started_at,
        authoritative_cycle_balance_usd=Decimal(
            balance
        ),
    )


def test_cycle_baseline_derives_price_book_truth(
    tmp_path,
):
    service, _ = build_service(
        tmp_path
    )

    result = create_baseline(
        service,
        balance="1200.00",
    )

    assert (
        result.authoritative_cycle_balance_usd
        == Decimal("1200.00")
    )

    assert (
        result.licensed_account_cap_usd
        == 2000
    )

    assert (
        result.standard_monthly_price_usd
        == 80
    )


def test_cycle_baseline_is_durable_and_immutable(
    tmp_path,
):
    service, store = build_service(
        tmp_path
    )

    created = create_baseline(
        service,
        balance="1000.00",
    )

    assert isinstance(
        created,
        CustomerCommercialBillingCycleBaselineRecord,
    )

    loaded = store.get(
        cycle_id=CYCLE_ID
    )

    assert loaded == created

    with pytest.raises(
        (
            AttributeError,
            TypeError,
        )
    ):
        created.standard_monthly_price_usd = 999


def test_identical_cycle_retry_is_idempotent(
    tmp_path,
):
    service, _ = build_service(
        tmp_path
    )

    first = create_baseline(
        service,
        balance="1000.00",
    )

    second = create_baseline(
        service,
        balance="1000.00",
    )

    assert second == first


@pytest.mark.parametrize(
    (
        "override",
        "expected_match",
    ),
    [
        (
            {
                "customer_id": "customer-other",
            },
            "cycle",
        ),
        (
            {
                "cycle_started_at": datetime(
                    2026,
                    9,
                    18,
                    0,
                    0,
                    tzinfo=UTC,
                ),
            },
            "cycle",
        ),
        (
            {
                "balance": "1000.01",
            },
            "cycle",
        ),
    ],
)
def test_same_cycle_id_cannot_change_authoritative_facts(
    tmp_path,
    override,
    expected_match,
):
    service, _ = build_service(
        tmp_path
    )

    create_baseline(
        service,
        balance="1000.00",
    )

    kwargs = {
        "cycle_id": CYCLE_ID,
        "customer_id": CUSTOMER_ID,
        "cycle_started_at": STARTED_AT,
        "balance": "1000.00",
    }

    kwargs.update(
        override
    )

    with pytest.raises(
        ValueError,
        match=expected_match,
    ):
        create_baseline(
            service,
            **kwargs,
        )


def test_later_live_balance_has_no_mutation_path(
    tmp_path,
):
    service, store = build_service(
        tmp_path
    )

    baseline = create_baseline(
        service,
        balance="1000.00",
    )

    # TODOBA may later trade the account to 1200, 1500,
    # or more. P9A3 has no live-balance mutation method.
    assert not hasattr(
        service,
        "update_balance",
    )

    assert not hasattr(
        service,
        "reprice_live_balance",
    )

    loaded = store.get(
        cycle_id=CYCLE_ID
    )

    assert loaded == baseline
    assert (
        loaded.authoritative_cycle_balance_usd
        == Decimal("1000.00")
    )
    assert (
        loaded.standard_monthly_price_usd
        == 50
    )


def test_restart_recovers_exact_cycle_baseline(
    tmp_path,
):
    path = (
        tmp_path
        / "commercial_billing_cycles.json"
    )

    first_store = (
        CustomerCommercialBillingCycleBaselineStore(
            path
        )
    )

    first_store.initialize_empty()

    first_service = (
        CustomerCommercialBillingCycleBaselineService(
            store=first_store,
            price_book=CustomerCommercialAccountPriceBook,
        )
    )

    expected = create_baseline(
        first_service,
        balance="7300.00",
    )

    restarted_store = (
        CustomerCommercialBillingCycleBaselineStore(
            path
        )
    )

    restarted_store.load()

    recovered = restarted_store.get(
        cycle_id=CYCLE_ID
    )

    assert recovered == expected
    assert (
        recovered.licensed_account_cap_usd
        == 8000
    )
    assert (
        recovered.standard_monthly_price_usd
        == 230
    )


@pytest.mark.parametrize(
    "invalid",
    [
        "",
        "   ",
        None,
        123,
    ],
)
def test_cycle_id_must_be_required_string(
    tmp_path,
    invalid,
):
    service, _ = build_service(
        tmp_path
    )

    with pytest.raises(
        (
            TypeError,
            ValueError,
        )
    ):
        service.create(
            cycle_id=invalid,
            customer_id=CUSTOMER_ID,
            cycle_started_at=STARTED_AT,
            authoritative_cycle_balance_usd=(
                Decimal("1000.00")
            ),
        )


def test_cycle_start_must_be_timezone_aware(
    tmp_path,
):
    service, _ = build_service(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="timezone",
    ):
        create_baseline(
            service,
            cycle_started_at=datetime(
                2026,
                9,
                17,
                0,
                0,
            ),
        )


def test_service_exposes_no_runtime_or_payment_authority(
    tmp_path,
):
    service, _ = build_service(
        tmp_path
    )

    for forbidden in (
        "observe_live_balance",
        "record_deposit",
        "record_withdrawal",
        "apply_grace",
        "upgrade",
        "downgrade",
        "settle",
        "activate",
        "grant_entitlement",
    ):
        assert not hasattr(
            service,
            forbidden,
        )
