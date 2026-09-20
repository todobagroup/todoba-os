from pathlib import Path

OWNER = Path(
    "backend/commercial/"
    "customer_commercial_pending_exposure_containment_issuance.py"
)


def test_containment_issuance_owner_exists():
    assert OWNER.exists()


def test_containment_issuance_is_durable_and_explicit():
    source = OWNER.read_text(
        encoding="utf-8-sig"
    )

    for required in (
        "CustomerCommercialPendingExposureContainmentIssuanceRecord",
        "CustomerCommercialPendingExposureContainmentIssuanceStore",
        "initialize_empty",
        "load",
        "save",
        "trigger_id",
        "deployment_id",
        "commercial_entitlement_id",
        "cycle_id",
        "agent_id",
        "account_fingerprint",
        "symbol",
        "mission_id",
        "requested_by_sender_id",
        "created_at",
        "expires_at",
        "sequence",
    ):
        assert required in source


def test_containment_issuance_does_not_own_broker_or_control_execution():
    source = OWNER.read_text(
        encoding="utf-8-sig"
    )

    for forbidden in (
        "ControlMissionService",
        "CANCEL_ALL_PENDING",
        "OrderDelete",
        "TRADE_ACTION_REMOVE",
        "PendingOrderRepository",
        "matched_pending_order_count",
        "canceled_pending_order_count",
    ):
        assert forbidden not in source


def test_containment_issuance_has_replay_lookup():
    source = OWNER.read_text(
        encoding="utf-8-sig"
    )

    assert "get_by_trigger_and_symbol" in source
# ===== P9F2B1A BEHAVIORAL CONTRACT =====

from dataclasses import replace

import pytest

import backend.commercial.customer_commercial_pending_exposure_containment_issuance as issuance_module

from backend.commercial.customer_commercial_pending_exposure_containment_issuance import (
    CustomerCommercialPendingExposureContainmentIssuanceRecord,
    CustomerCommercialPendingExposureContainmentIssuanceStore,
)


def _issuance_record(
    *,
    issuance_id: str = "containment-issuance-1",
    trigger_id: str = "funding-trigger-1",
    symbol: str = "EURUSD",
    mission_id: str = "containment-mission-1",
    sequence: int = 1,
) -> CustomerCommercialPendingExposureContainmentIssuanceRecord:
    return CustomerCommercialPendingExposureContainmentIssuanceRecord(
        issuance_id=issuance_id,
        trigger_id=trigger_id,
        deployment_id="deployment-1",
        commercial_entitlement_id="entitlement-1",
        cycle_id="cycle-1",
        agent_id="trusted-agent-1",
        account_fingerprint="RoboForex-Pro:68353796",
        symbol=symbol,
        mission_id=mission_id,
        requested_by_sender_id=1,
        created_at="2026-09-20T02:00:00Z",
        expires_at="2026-09-20T02:02:00Z",
        sequence=sequence,
    )


def test_containment_issuance_identical_replay_is_idempotent(
    tmp_path,
):
    store = CustomerCommercialPendingExposureContainmentIssuanceStore(
        tmp_path / "containment.json"
    )
    store.initialize_empty()

    record = _issuance_record()

    first = store.save(record)
    second = store.save(record)

    assert first == record
    assert second == record
    assert (
        store.get_by_trigger_and_symbol(
            trigger_id=record.trigger_id,
            symbol=record.symbol,
        )
        == record
    )
    assert (
        store.get_by_mission_id(
            record.mission_id
        )
        == record
    )


def test_containment_issuance_conflicting_replay_fails_closed(
    tmp_path,
):
    store = CustomerCommercialPendingExposureContainmentIssuanceStore(
        tmp_path / "containment.json"
    )
    store.initialize_empty()

    record = _issuance_record()
    store.save(record)

    conflict = replace(
        record,
        mission_id="containment-mission-2",
    )

    with pytest.raises(
        ValueError,
        match="replay conflict",
    ):
        store.save(conflict)

    assert (
        store.get_by_trigger_and_symbol(
            trigger_id=record.trigger_id,
            symbol=record.symbol,
        )
        == record
    )


def test_containment_issuance_duplicate_mission_id_fails_closed(
    tmp_path,
):
    store = CustomerCommercialPendingExposureContainmentIssuanceStore(
        tmp_path / "containment.json"
    )
    store.initialize_empty()

    first = _issuance_record()
    store.save(first)

    second = _issuance_record(
        issuance_id="containment-issuance-2",
        trigger_id="funding-trigger-2",
        symbol="GBPUSD",
        mission_id=first.mission_id,
        sequence=2,
    )

    with pytest.raises(
        ValueError,
        match="mission_id already belongs",
    ):
        store.save(second)

    assert (
        store.get_by_trigger_and_symbol(
            trigger_id=second.trigger_id,
            symbol=second.symbol,
        )
        is None
    )


def test_containment_issuance_survives_restart(
    tmp_path,
):
    path = tmp_path / "containment.json"

    original = CustomerCommercialPendingExposureContainmentIssuanceStore(
        path
    )
    original.initialize_empty()

    record = _issuance_record()
    original.save(record)

    recovered = CustomerCommercialPendingExposureContainmentIssuanceStore(
        path
    )
    recovered.load()

    assert recovered.is_ready() is True
    assert (
        recovered.get_by_trigger_and_symbol(
            trigger_id=record.trigger_id,
            symbol=record.symbol,
        )
        == record
    )
    assert (
        recovered.get_by_mission_id(
            record.mission_id
        )
        == record
    )


def test_containment_issuance_persistence_failure_does_not_advance_ram(
    tmp_path,
    monkeypatch,
):
    store = CustomerCommercialPendingExposureContainmentIssuanceStore(
        tmp_path / "containment.json"
    )
    store.initialize_empty()

    record = _issuance_record()

    def fail_replace(
        source,
        destination,
    ):
        raise OSError(
            "simulated persistence failure"
        )

    monkeypatch.setattr(
        issuance_module.os,
        "replace",
        fail_replace,
    )

    with pytest.raises(
        RuntimeError,
        match="could not be persisted",
    ):
        store.save(record)

    assert (
        store.get_by_trigger_and_symbol(
            trigger_id=record.trigger_id,
            symbol=record.symbol,
        )
        is None
    )
    assert (
        store.get_by_mission_id(
            record.mission_id
        )
        is None
    )
