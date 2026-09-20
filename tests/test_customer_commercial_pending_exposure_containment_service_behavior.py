from __future__ import annotations

import importlib
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from backend.commercial.customer_commercial_capacity_decision_service import (
    CustomerCommercialCapacityDecisionStatus,
)
from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission_issuance_scope import (
    INTERNAL_COMMERCIAL_CONTROL_SENDER_ID,
    TODOBA_MAGIC_NUMBER,
)


SERVICE_MODULE = (
    "backend.commercial."
    "customer_commercial_pending_exposure_containment_service"
)


class FakeDeploymentBindingStore:
    def __init__(self, binding):
        self.binding = binding
        self.requested_deployment_ids = []

    def get_by_deployment_id(
        self,
        *,
        deployment_id: str,
    ):
        self.requested_deployment_ids.append(
            deployment_id
        )

        if (
            self.binding is not None
            and self.binding.deployment_id
            == deployment_id
        ):
            return self.binding

        return None


class FakeCapacityDecisionProvider:
    def __init__(self, decision):
        self.decision = decision
        self.requested_deployment_ids = []

    def provide(
        self,
        *,
        deployment_id: str,
    ):
        self.requested_deployment_ids.append(
            deployment_id
        )
        return self.decision


class FakeIssuanceStore:
    def __init__(self):
        self.records = {}
        self.saved = []

    def get_by_trigger_and_symbol(
        self,
        *,
        trigger_id: str,
        symbol: str,
    ):
        return self.records.get(
            (trigger_id, symbol)
        )

    def save(self, record):
        key = (
            record.trigger_id,
            record.symbol,
        )

        existing = self.records.get(key)

        if (
            existing is not None
            and existing != record
        ):
            raise ValueError(
                "Containment issuance replay conflict."
            )

        self.records[key] = record
        self.saved.append(record)
        return record


class FakeControlMissionService:
    def __init__(self):
        self.created = []

    def create_mission(self, mission):
        self.created.append(mission)
        return mission


def _load_owner():
    return importlib.import_module(
        SERVICE_MODULE
    )


def _binding():
    return SimpleNamespace(
        commercial_entitlement_id="entitlement-001",
        customer_id="customer-001",
        deployment_id="deployment-001",
        agent_id="trusted-agent-001",
        account_fingerprint="Broker:123456",
    )


def _decision(status):
    return SimpleNamespace(
        commercial_entitlement_id="entitlement-001",
        deployment_id="deployment-001",
        cycle_id="cycle-001",
        status=status,
    )


def _fixed_now():
    return datetime(
        2026,
        9,
        20,
        3,
        45,
        0,
        tzinfo=UTC,
    )


def _build_service(
    *,
    status=(
        CustomerCommercialCapacityDecisionStatus
        .UPGRADE_REQUIRED
    ),
):
    module = _load_owner()

    binding_store = FakeDeploymentBindingStore(
        _binding()
    )
    capacity_provider = (
        FakeCapacityDecisionProvider(
            _decision(status)
        )
    )
    issuance_store = FakeIssuanceStore()
    control_service = FakeControlMissionService()

    service = (
        module.CustomerCommercialPendingExposureContainmentService(
            deployment_binding_store=binding_store,
            capacity_decision_provider=(
                capacity_provider
            ),
            issuance_store=issuance_store,
            control_mission_service=(
                control_service
            ),
            now_provider=_fixed_now,
        )
    )

    return (
        module,
        service,
        binding_store,
        capacity_provider,
        issuance_store,
        control_service,
    )


def test_rejects_without_upgrade_required():
    (
        _,
        service,
        _,
        capacity_provider,
        issuance_store,
        control_service,
    ) = _build_service(
        status=(
            CustomerCommercialCapacityDecisionStatus
            .ALLOW_NEW_EXPOSURE
        )
    )

    with pytest.raises(
        RuntimeError,
        match="UPGRADE_REQUIRED",
    ):
        service.issue(
            trigger_id="funding-trigger-001",
            deployment_id="deployment-001",
        )

    assert capacity_provider.requested_deployment_ids == [
        "deployment-001"
    ]
    assert issuance_store.saved == []
    assert control_service.created == []


def test_uses_authoritative_deployment_identity():
    (
        _,
        service,
        binding_store,
        capacity_provider,
        _,
        control_service,
    ) = _build_service()

    missions = service.issue(
        trigger_id="funding-trigger-001",
        deployment_id="deployment-001",
    )

    assert binding_store.requested_deployment_ids == [
        "deployment-001"
    ]
    assert capacity_provider.requested_deployment_ids == [
        "deployment-001"
    ]

    assert missions

    for mission in missions:
        assert (
            mission.agent_id
            == "trusted-agent-001"
        )
        assert (
            mission.account_fingerprint
            == "Broker:123456"
        )

    assert control_service.created == list(
        missions
    )


def test_issues_cancel_all_pending_for_every_authoritative_symbol(
    monkeypatch,
):
    (
        module,
        service,
        _,
        _,
        issuance_store,
        _,
    ) = _build_service()

    monkeypatch.setattr(
        module,
        "PRODUCTION_CONTROL_ALLOWED_SYMBOLS",
        (
            "XAUUSD",
            "EURUSD",
        ),
    )

    missions = service.issue(
        trigger_id="funding-trigger-001",
        deployment_id="deployment-001",
    )

    assert tuple(
        mission.symbol
        for mission in missions
    ) == (
        "XAUUSD",
        "EURUSD",
    )

    for mission in missions:
        assert (
            mission.action
            == ControlAction.CANCEL_ALL_PENDING
        )
        assert (
            mission.magic_number
            == TODOBA_MAGIC_NUMBER
        )
        assert (
            mission.requested_by_sender_id
            == INTERNAL_COMMERCIAL_CONTROL_SENDER_ID
        )
        assert mission.sequence > 0

    assert len(issuance_store.saved) == 2


def test_freezes_two_minute_freshness_window():
    (
        _,
        service,
        _,
        _,
        issuance_store,
        _,
    ) = _build_service()

    service.issue(
        trigger_id="funding-trigger-001",
        deployment_id="deployment-001",
    )

    assert len(issuance_store.saved) == 1

    record = issuance_store.saved[0]

    created = datetime.fromisoformat(
        record.created_at.replace(
            "Z",
            "+00:00",
        )
    )
    expires = datetime.fromisoformat(
        record.expires_at.replace(
            "Z",
            "+00:00",
        )
    )

    assert (
        expires - created
    ).total_seconds() == 120


def test_retry_reuses_exact_frozen_issuance():
    (
        _,
        service,
        _,
        _,
        issuance_store,
        control_service,
    ) = _build_service()

    first = service.issue(
        trigger_id="funding-trigger-001",
        deployment_id="deployment-001",
    )

    saved_after_first = tuple(
        issuance_store.saved
    )

    second = service.issue(
        trigger_id="funding-trigger-001",
        deployment_id="deployment-001",
    )

    assert tuple(
        issuance_store.saved
    ) == saved_after_first

    assert len(first) == len(second) == 1

    first_mission = first[0]
    second_mission = second[0]

    assert (
        first_mission.mission_id
        == second_mission.mission_id
    )
    assert (
        first_mission.sequence
        == second_mission.sequence
    )
    assert (
        first_mission.created_at
        == second_mission.created_at
    )
    assert (
        first_mission.expires_at
        == second_mission.expires_at
    )
    assert (
        first_mission.agent_id
        == second_mission.agent_id
    )
    assert (
        first_mission.account_fingerprint
        == second_mission.account_fingerprint
    )

    assert len(control_service.created) == 2


def test_rejects_decision_binding_identity_mismatch():
    module = _load_owner()

    binding_store = FakeDeploymentBindingStore(
        _binding()
    )

    mismatched_decision = SimpleNamespace(
        commercial_entitlement_id=(
            "entitlement-DIFFERENT"
        ),
        deployment_id="deployment-001",
        cycle_id="cycle-001",
        status=(
            CustomerCommercialCapacityDecisionStatus
            .UPGRADE_REQUIRED
        ),
    )

    capacity_provider = (
        FakeCapacityDecisionProvider(
            mismatched_decision
        )
    )

    issuance_store = FakeIssuanceStore()
    control_service = FakeControlMissionService()

    service = (
        module.CustomerCommercialPendingExposureContainmentService(
            deployment_binding_store=binding_store,
            capacity_decision_provider=(
                capacity_provider
            ),
            issuance_store=issuance_store,
            control_mission_service=(
                control_service
            ),
            now_provider=_fixed_now,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="identity",
    ):
        service.issue(
            trigger_id="funding-trigger-001",
            deployment_id="deployment-001",
        )

    assert issuance_store.saved == []
    assert control_service.created == []
