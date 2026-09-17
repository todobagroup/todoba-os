"""
P9A4C ? In-Cycle External Funding Observation.

Durably observes broker-qualified external funding
against an existing commercial billing cycle.

This capability does NOT:
- classify MT5 evidence
- own pricing
- apply licensed-cap grace
- decide upgrade
- block runtime execution
- own settlement or entitlement authority
"""

from decimal import Decimal

import pytest

from backend.commercial.customer_commercial_account_price_book import (
    CustomerCommercialAccountPriceBook,
)

from backend.commercial.customer_commercial_billing_cycle_baseline_service import (
    CustomerCommercialBillingCycleBaselineService,
    CustomerCommercialBillingCycleBaselineStore,
)

from backend.commercial.customer_commercial_external_funding_observation_service import (
    CustomerCommercialExternalFundingObservationService,
    CustomerCommercialExternalFundingObservationStore,
)

from backend.trading.lifecycle.mt5_external_funding_classifier import (
    MT5ExternalFundingClassification,
)


CYCLE_ID = "billing-cycle-p9a4c-001"
ACCOUNT = "RoboForex-Pro:68353796"
DEAL_TICKET = 2254467273


def ready_cycle_store(tmp_path):
    path = tmp_path / "billing-cycles.json"

    store = CustomerCommercialBillingCycleBaselineStore(
        path
    )
    store.initialize_empty()

    service = CustomerCommercialBillingCycleBaselineService(
        store=store,
        price_book=CustomerCommercialAccountPriceBook,
    )

    service.create(
        cycle_id=CYCLE_ID,
        customer_id="customer-p9a4c-001",
        cycle_started_at=__import__(
            "datetime"
        ).datetime(
            2026,
            9,
            1,
            tzinfo=__import__(
                "datetime"
            ).UTC,
        ),
        authoritative_cycle_balance_usd=Decimal(
            "8000"
        ),
    )

    return store


def classification(
    *,
    kind="external_deposit",
    account_fingerprint=ACCOUNT,
    deal_ticket=DEAL_TICKET,
    amount=Decimal("8000"),
):
    return MT5ExternalFundingClassification(
        kind=kind,
        account_fingerprint=account_fingerprint,
        deal_ticket=deal_ticket,
        amount=amount,
    )


def ready_observation_store(tmp_path):
    store = CustomerCommercialExternalFundingObservationStore(
        tmp_path / "external-funding-observations.json"
    )
    store.initialize_empty()
    return store


def service(tmp_path):
    return CustomerCommercialExternalFundingObservationService(
        store=ready_observation_store(
            tmp_path
        ),
        billing_cycle_store=ready_cycle_store(
            tmp_path
        ),
    )


def test_external_deposit_is_durably_observed(tmp_path):
    svc = service(tmp_path)

    record = svc.observe(
        cycle_id=CYCLE_ID,
        classification=classification(),
    )

    assert record.cycle_id == CYCLE_ID
    assert record.account_fingerprint == ACCOUNT
    assert record.deal_ticket == DEAL_TICKET
    assert record.funding_kind == "external_deposit"
    assert record.amount == Decimal("8000")


def test_exact_retry_is_idempotent(tmp_path):
    svc = service(tmp_path)

    first = svc.observe(
        cycle_id=CYCLE_ID,
        classification=classification(),
    )

    second = svc.observe(
        cycle_id=CYCLE_ID,
        classification=classification(),
    )

    assert second == first


def test_replay_identity_is_global_across_cycles(tmp_path):
    cycle_store = ready_cycle_store(
        tmp_path
    )

    cycle_service = CustomerCommercialBillingCycleBaselineService(
        store=cycle_store,
        price_book=CustomerCommercialAccountPriceBook,
    )

    cycle_service.create(
        cycle_id="billing-cycle-p9a4c-002",
        customer_id="customer-p9a4c-001",
        cycle_started_at=__import__(
            "datetime"
        ).datetime(
            2026,
            10,
            1,
            tzinfo=__import__(
                "datetime"
            ).UTC,
        ),
        authoritative_cycle_balance_usd=Decimal(
            "8000"
        ),
    )

    obs_store = ready_observation_store(
        tmp_path
    )

    svc = CustomerCommercialExternalFundingObservationService(
        store=obs_store,
        billing_cycle_store=cycle_store,
    )

    svc.observe(
        cycle_id=CYCLE_ID,
        classification=classification(),
    )

    with pytest.raises(
        ValueError,
        match="replay",
    ):
        svc.observe(
            cycle_id="billing-cycle-p9a4c-002",
            classification=classification(),
        )


def test_replay_cannot_change_amount(tmp_path):
    svc = service(tmp_path)

    svc.observe(
        cycle_id=CYCLE_ID,
        classification=classification(),
    )

    with pytest.raises(
        ValueError,
        match="replay",
    ):
        svc.observe(
            cycle_id=CYCLE_ID,
            classification=classification(
                amount=Decimal("9000")
            ),
        )


def test_replay_cannot_change_funding_kind(tmp_path):
    svc = service(tmp_path)

    svc.observe(
        cycle_id=CYCLE_ID,
        classification=classification(),
    )

    with pytest.raises(
        ValueError,
        match="replay",
    ):
        svc.observe(
            cycle_id=CYCLE_ID,
            classification=classification(
                kind="external_withdrawal",
                amount=Decimal("-8000"),
            ),
        )


def test_unknown_is_not_persisted(tmp_path):
    svc = service(tmp_path)

    with pytest.raises(
        ValueError,
        match="external",
    ):
        svc.observe(
            cycle_id=CYCLE_ID,
            classification=classification(
                kind="unknown"
            ),
        )


def test_not_external_is_not_persisted(tmp_path):
    svc = service(tmp_path)

    with pytest.raises(
        ValueError,
        match="external",
    ):
        svc.observe(
            cycle_id=CYCLE_ID,
            classification=classification(
                kind="not_external"
            ),
        )


def test_cycle_must_exist(tmp_path):
    svc = service(tmp_path)

    with pytest.raises(
        ValueError,
        match="cycle",
    ):
        svc.observe(
            cycle_id="missing-cycle",
            classification=classification(),
        )


def test_observation_survives_restart(tmp_path):
    observation_path = (
        tmp_path
        / "external-funding-observations.json"
    )

    cycle_store = ready_cycle_store(
        tmp_path
    )

    first_store = (
        CustomerCommercialExternalFundingObservationStore(
            observation_path
        )
    )
    first_store.initialize_empty()

    first_service = (
        CustomerCommercialExternalFundingObservationService(
            store=first_store,
            billing_cycle_store=cycle_store,
        )
    )

    expected = first_service.observe(
        cycle_id=CYCLE_ID,
        classification=classification(),
    )

    restored_store = (
        CustomerCommercialExternalFundingObservationStore(
            observation_path
        )
    )
    restored_store.load()

    restored_service = (
        CustomerCommercialExternalFundingObservationService(
            store=restored_store,
            billing_cycle_store=cycle_store,
        )
    )

    restored = restored_service.get_by_replay_identity(
        account_fingerprint=ACCOUNT,
        deal_ticket=DEAL_TICKET,
    )

    assert restored == expected


def test_uninitialized_observation_store_fails_closed(
    tmp_path,
):
    observation_store = (
        CustomerCommercialExternalFundingObservationStore(
            tmp_path / "not-initialized.json"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="initialized",
    ):
        CustomerCommercialExternalFundingObservationService(
            store=observation_store,
            billing_cycle_store=ready_cycle_store(
                tmp_path
            ),
        )


def test_uninitialized_cycle_store_fails_closed(
    tmp_path,
):
    observation_store = ready_observation_store(
        tmp_path
    )

    cycle_store = CustomerCommercialBillingCycleBaselineStore(
        tmp_path / "uninitialized-cycle-store.json"
    )

    with pytest.raises(
        RuntimeError,
        match="initialized",
    ):
        CustomerCommercialExternalFundingObservationService(
            store=observation_store,
            billing_cycle_store=cycle_store,
        )


def test_store_restores_replay_identity_not_cycle_scoped(
    tmp_path,
):
    path = tmp_path / "external-funding-observations.json"

    store = CustomerCommercialExternalFundingObservationStore(
        path
    )
    store.initialize_empty()

    svc = CustomerCommercialExternalFundingObservationService(
        store=store,
        billing_cycle_store=ready_cycle_store(
            tmp_path
        ),
    )

    svc.observe(
        cycle_id=CYCLE_ID,
        classification=classification(),
    )

    restored = CustomerCommercialExternalFundingObservationStore(
        path
    )
    restored.load()

    assert restored.get_by_replay_identity(
        account_fingerprint=ACCOUNT,
        deal_ticket=DEAL_TICKET,
    ) is not None


def test_service_has_no_capacity_or_upgrade_authority(
    tmp_path,
):
    svc = service(tmp_path)

    for forbidden in (
        "licensed_account_cap_usd",
        "grace_percent",
        "grace_ceiling_usd",
        "upgrade_required",
        "runtime_blocked",
        "payment_intent_id",
        "settlement_id",
        "entitlement_id",
    ):
        assert not hasattr(
            svc,
            forbidden,
        )
