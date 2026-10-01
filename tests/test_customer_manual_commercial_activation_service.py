from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.commercial.customer_manual_commercial_activation_service import (
    CustomerManualCommercialActivationService,
    CustomerManualCommercialActivationStore,
)


class RecordingRegistrationService:
    def __init__(self):
        self.calls = []

    def register(self, *, registration_request_id):
        self.calls.append(registration_request_id)

        return SimpleNamespace(
            registration_request_id=registration_request_id,
            customer_id="customer-authoritative-001",
        )


class RecordingActivationService:
    def __init__(self):
        self.calls = []

    def activate(
        self,
        *,
        activation_request_id,
        customer_id,
    ):
        self.calls.append(
            (
                activation_request_id,
                customer_id,
            )
        )

        return SimpleNamespace(
            activation_request_id=activation_request_id,
            setup_activation_id=(
                "setup-activation-manual-001"
            ),
            customer_id=customer_id,
            status=SimpleNamespace(
                value="ACTIVE"
            ),
        )


def _build(
    tmp_path: Path,
):
    store = CustomerManualCommercialActivationStore(
        tmp_path / "manual-approvals.json"
    )
    store.open_or_initialize()

    registrations = RecordingRegistrationService()
    activations = RecordingActivationService()

    service = CustomerManualCommercialActivationService(
        approval_store=store,
        registration_service=registrations,
        setup_activation_service=activations,
    )

    return (
        service,
        store,
        registrations,
        activations,
    )


def test_manual_approval_resolves_customer_and_activates(
    tmp_path,
):
    (
        service,
        _,
        registrations,
        activations,
    ) = _build(tmp_path)

    result = service.approve(
        manual_approval_request_id="manual-sale-001",
        registration_request_id="registration-001",
        operator_id="operator-001",
    )

    assert registrations.calls == [
        "registration-001"
    ]

    assert activations.calls == [
        (
            "manual-commercial-activation-manual-sale-001",
            "customer-authoritative-001",
        )
    ]

    assert result.manual_approval_request_id == (
        "manual-sale-001"
    )
    assert result.registration_request_id == (
        "registration-001"
    )
    assert result.operator_id == "operator-001"
    assert result.customer_id == (
        "customer-authoritative-001"
    )
    assert result.setup_activation_id == (
        "setup-activation-manual-001"
    )


def test_service_exposes_no_payment_or_code_authority(
    tmp_path,
):
    service, _, _, _ = _build(tmp_path)

    forbidden = (
        "settle",
        "mark_paid",
        "verify_payment",
        "build_assertion",
        "complete_verified_payment",
        "issue",
        "issue_once",
    )

    for name in forbidden:
        assert not hasattr(service, name)


def test_same_approval_request_is_idempotent(
    tmp_path,
):
    service, store, _, _ = _build(tmp_path)

    first = service.approve(
        manual_approval_request_id="manual-sale-001",
        registration_request_id="registration-001",
        operator_id="operator-001",
    )

    second = service.approve(
        manual_approval_request_id="manual-sale-001",
        registration_request_id="registration-001",
        operator_id="operator-001",
    )

    assert second == first
    assert len(store.all()) == 1


def test_same_approval_cannot_move_to_other_registration(
    tmp_path,
):
    service, _, _, _ = _build(tmp_path)

    service.approve(
        manual_approval_request_id="manual-sale-001",
        registration_request_id="registration-001",
        operator_id="operator-001",
    )

    with pytest.raises(
        ValueError,
        match="already bound to different facts",
    ):
        service.approve(
            manual_approval_request_id="manual-sale-001",
            registration_request_id="registration-002",
            operator_id="operator-001",
        )


def test_same_approval_cannot_move_to_other_operator(
    tmp_path,
):
    service, _, _, _ = _build(tmp_path)

    service.approve(
        manual_approval_request_id="manual-sale-001",
        registration_request_id="registration-001",
        operator_id="operator-001",
    )

    with pytest.raises(
        ValueError,
        match="already bound to different facts",
    ):
        service.approve(
            manual_approval_request_id="manual-sale-001",
            registration_request_id="registration-001",
            operator_id="operator-002",
        )


def test_approval_survives_restart(
    tmp_path,
):
    service, store, _, _ = _build(tmp_path)

    first = service.approve(
        manual_approval_request_id="manual-sale-001",
        registration_request_id="registration-001",
        operator_id="operator-001",
    )

    restarted_store = (
        CustomerManualCommercialActivationStore(
            store.storage_path
        )
    )
    restarted_store.open_or_initialize()

    restarted = restarted_store.get(
        manual_approval_request_id="manual-sale-001"
    )

    assert restarted is not None
    assert restarted.setup_activation_id == (
        first.setup_activation_id
    )
    assert restarted.customer_id == first.customer_id


def test_store_conflicting_retry_does_not_mutate_durable_state(
    tmp_path,
):
    service, store, _, _ = _build(tmp_path)

    service.approve(
        manual_approval_request_id="manual-sale-001",
        registration_request_id="registration-001",
        operator_id="operator-001",
    )

    before = store.storage_path.read_bytes()

    with pytest.raises(ValueError):
        service.approve(
            manual_approval_request_id="manual-sale-001",
            registration_request_id="registration-002",
            operator_id="operator-001",
        )

    assert store.storage_path.read_bytes() == before
