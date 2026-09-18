from decimal import Decimal

import pytest

from backend.commercial.customer_commercial_external_funding_observation_service import (
    CustomerCommercialExternalFundingObservationRecord,
    CustomerCommercialExternalFundingObservationStore,
)


def _record(
    *,
    cycle_id: str,
    account_fingerprint: str,
    deal_ticket: int,
    funding_kind: str,
    amount: str,
) -> CustomerCommercialExternalFundingObservationRecord:
    return CustomerCommercialExternalFundingObservationRecord(
        cycle_id=cycle_id,
        account_fingerprint=account_fingerprint,
        deal_ticket=deal_ticket,
        funding_kind=funding_kind,
        amount=Decimal(amount),
    )


def _ready_store(tmp_path):
    store = CustomerCommercialExternalFundingObservationStore(
        tmp_path / "external-funding.json"
    )
    store.initialize_empty()
    return store


def test_projection_returns_exact_cycle_and_account_only(
    tmp_path,
) -> None:
    store = _ready_store(tmp_path)

    expected_deposit = _record(
        cycle_id="cycle-001",
        account_fingerprint="Broker-Pro:1001",
        deal_ticket=101,
        funding_kind="external_deposit",
        amount="250",
    )

    expected_withdrawal = _record(
        cycle_id="cycle-001",
        account_fingerprint="Broker-Pro:1001",
        deal_ticket=102,
        funding_kind="external_withdrawal",
        amount="-50",
    )

    store.save(expected_deposit)
    store.save(expected_withdrawal)

    store.save(
        _record(
            cycle_id="cycle-002",
            account_fingerprint="Broker-Pro:1001",
            deal_ticket=201,
            funding_kind="external_deposit",
            amount="500",
        )
    )

    store.save(
        _record(
            cycle_id="cycle-001",
            account_fingerprint="Broker-Pro:2002",
            deal_ticket=301,
            funding_kind="external_deposit",
            amount="700",
        )
    )

    result = store.list_by_cycle_and_account(
        cycle_id="cycle-001",
        account_fingerprint="Broker-Pro:1001",
    )

    assert result == (
        expected_deposit,
        expected_withdrawal,
    )


def test_projection_returns_empty_tuple_when_no_match(
    tmp_path,
) -> None:
    store = _ready_store(tmp_path)

    assert (
        store.list_by_cycle_and_account(
            cycle_id="cycle-missing",
            account_fingerprint="Broker-Pro:1001",
        )
        == ()
    )


def test_projection_is_deterministic_by_deal_ticket(
    tmp_path,
) -> None:
    store = _ready_store(tmp_path)

    high_ticket = _record(
        cycle_id="cycle-001",
        account_fingerprint="Broker-Pro:1001",
        deal_ticket=300,
        funding_kind="external_deposit",
        amount="30",
    )

    low_ticket = _record(
        cycle_id="cycle-001",
        account_fingerprint="Broker-Pro:1001",
        deal_ticket=100,
        funding_kind="external_deposit",
        amount="10",
    )

    mid_ticket = _record(
        cycle_id="cycle-001",
        account_fingerprint="Broker-Pro:1001",
        deal_ticket=200,
        funding_kind="external_withdrawal",
        amount="-5",
    )

    store.save(high_ticket)
    store.save(low_ticket)
    store.save(mid_ticket)

    result = store.list_by_cycle_and_account(
        cycle_id="cycle-001",
        account_fingerprint="Broker-Pro:1001",
    )

    assert result == (
        low_ticket,
        mid_ticket,
        high_ticket,
    )


def test_projection_returns_tuple_not_mutable_collection(
    tmp_path,
) -> None:
    store = _ready_store(tmp_path)

    result = store.list_by_cycle_and_account(
        cycle_id="cycle-001",
        account_fingerprint="Broker-Pro:1001",
    )

    assert isinstance(
        result,
        tuple,
    )


@pytest.mark.parametrize(
    (
        "cycle_id",
        "account_fingerprint",
    ),
    (
        ("", "Broker-Pro:1001"),
        ("   ", "Broker-Pro:1001"),
        ("cycle-001", ""),
        ("cycle-001", "   "),
    ),
)
def test_projection_rejects_blank_identity(
    tmp_path,
    cycle_id,
    account_fingerprint,
) -> None:
    store = _ready_store(tmp_path)

    with pytest.raises(
        ValueError,
    ):
        store.list_by_cycle_and_account(
            cycle_id=cycle_id,
            account_fingerprint=account_fingerprint,
        )


def test_projection_fails_closed_when_store_not_ready(
    tmp_path,
) -> None:
    store = CustomerCommercialExternalFundingObservationStore(
        tmp_path / "external-funding.json"
    )

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        store.list_by_cycle_and_account(
            cycle_id="cycle-001",
            account_fingerprint="Broker-Pro:1001",
        )
