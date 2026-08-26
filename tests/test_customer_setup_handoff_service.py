"""
TODOBA Customer Setup Handoff Service Tests

Owner contract:
- handoff credentials are short-lived opaque bearer secrets
- durable state stores only SHA-256 verifier, never plaintext
- lifetime is fixed at 30 minutes
- expiration is computed, not persisted as a status
- expiration boundary is current_time >= expires_at
- ACTIVE and BOUND setup activations may authorize
- SUSPENDED setup activations fail closed
- issuance retry keeps handoff_id and lifetime
- issuance retry rotates plaintext secret and verifier
- issuance retry cannot revive REVOKED or expired handoffs
- a new issuance request supersedes the previous ACTIVE handoff
- at most one ACTIVE handoff exists per setup activation
- verifier comparison uses constant-time compare_digest
- restart restores all security indexes
- orphaned setup-activation references fail closed
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.commercial.customer_setup_handoff_service as handoff_module
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationRecord,
    CustomerSetupActivationStatus,
    CustomerSetupActivationStore,
)
from backend.commercial.customer_setup_handoff_service import (
    CustomerSetupHandoffAuthorization,
    CustomerSetupHandoffIssuanceResult,
    CustomerSetupHandoffRecord,
    CustomerSetupHandoffService,
    CustomerSetupHandoffStatus,
    CustomerSetupHandoffStore,
    derive_customer_setup_handoff_verifier,
)


NOW = datetime(
    2026,
    8,
    26,
    10,
    0,
    0,
    tzinfo=timezone.utc,
)

HANDOFF_ID_A = "a" * 32
HANDOFF_ID_B = "b" * 32
VERIFIER_A = "a" * 64
VERIFIER_B = "b" * 64


def build_environment(
    tmp_path: Path,
) -> tuple[
    CustomerSetupActivationStore,
    CustomerSetupHandoffStore,
    CustomerSetupHandoffService,
]:
    activation_store = CustomerSetupActivationStore(
        tmp_path
        / "customer_setup_activations.json"
    )
    activation_store.initialize_empty()

    handoff_store = CustomerSetupHandoffStore(
        tmp_path
        / "customer_setup_handoffs.json"
    )
    handoff_store.initialize_empty()

    service = CustomerSetupHandoffService(
        handoff_store=handoff_store,
        setup_activation_store=activation_store,
    )

    return (
        activation_store,
        handoff_store,
        service,
    )


def create_active_activation(
    activation_store: CustomerSetupActivationStore,
    *,
    request_id: str = "activation-request-001",
    setup_activation_id: str = "setup-activation-001",
    customer_id: str = "customer-001",
) -> CustomerSetupActivationRecord:
    return activation_store.register(
        CustomerSetupActivationRecord(
            activation_request_id=request_id,
            setup_activation_id=setup_activation_id,
            customer_id=customer_id,
            status=(
                CustomerSetupActivationStatus.ACTIVE
            ),
        )
    )


def create_suspended_activation(
    activation_store: CustomerSetupActivationStore,
    *,
    setup_activation_id: str = "setup-activation-001",
) -> CustomerSetupActivationRecord:
    active = create_active_activation(
        activation_store,
        setup_activation_id=setup_activation_id,
    )

    return activation_store.suspend(
        setup_activation_id=(
            active.setup_activation_id
        )
    )


def create_bound_activation(
    activation_store: CustomerSetupActivationStore,
    *,
    setup_activation_id: str = "setup-activation-001",
    deployment_id: str = "deployment-001",
) -> CustomerSetupActivationRecord:
    active = create_active_activation(
        activation_store,
        setup_activation_id=setup_activation_id,
    )

    return activation_store.bind(
        setup_activation_id=(
            active.setup_activation_id
        ),
        deployment_id=deployment_id,
    )


def build_record(
    *,
    issuance_request_id: str = "handoff-request-001",
    handoff_id: str = HANDOFF_ID_A,
    setup_activation_id: str = "setup-activation-001",
    verifier_sha256: str = VERIFIER_A,
    issued_at: str = "2026-08-26T10:00:00Z",
    expires_at: str = "2026-08-26T10:30:00Z",
    status: CustomerSetupHandoffStatus = (
        CustomerSetupHandoffStatus.ACTIVE
    ),
) -> CustomerSetupHandoffRecord:
    return CustomerSetupHandoffRecord(
        issuance_request_id=issuance_request_id,
        handoff_id=handoff_id,
        setup_activation_id=setup_activation_id,
        verifier_sha256=verifier_sha256,
        issued_at=issued_at,
        expires_at=expires_at,
        status=status,
    )


def test_status_values_are_locked() -> None:
    assert tuple(
        item.value
        for item in CustomerSetupHandoffStatus
    ) == (
        "ACTIVE",
        "REVOKED",
    )


def test_record_normalizes_fields_and_timestamps() -> None:
    record = CustomerSetupHandoffRecord(
        issuance_request_id=" request-001 ",
        handoff_id=HANDOFF_ID_A,
        setup_activation_id=" setup-activation-001 ",
        verifier_sha256="A" * 64,
        issued_at="2026-08-26T17:00:00+07:00",
        expires_at="2026-08-26T17:30:00+07:00",
        status=(
            CustomerSetupHandoffStatus.ACTIVE
        ),
    )

    assert (
        record.issuance_request_id
        == "request-001"
    )
    assert (
        record.setup_activation_id
        == "setup-activation-001"
    )
    assert record.verifier_sha256 == "a" * 64
    assert record.issued_at == "2026-08-26T10:00:00Z"
    assert (
        record.expires_at
        == "2026-08-26T10:30:00Z"
    )


@pytest.mark.parametrize(
    "field_name",
    [
        "issuance_request_id",
        "setup_activation_id",
    ],
)
def test_record_rejects_empty_required_identity(
    field_name: str,
) -> None:
    values = {
        "issuance_request_id": "request-001",
        "handoff_id": HANDOFF_ID_A,
        "setup_activation_id": (
            "setup-activation-001"
        ),
        "verifier_sha256": VERIFIER_A,
        "issued_at": "2026-08-26T10:00:00Z",
        "expires_at": "2026-08-26T10:30:00Z",
        "status": (
            CustomerSetupHandoffStatus.ACTIVE
        ),
    }

    values[field_name] = "   "

    with pytest.raises(
        ValueError,
        match=f"{field_name} is required",
    ):
        CustomerSetupHandoffRecord(
            **values,
        )


def test_record_rejects_empty_handoff_id() -> None:
    with pytest.raises(
        ValueError,
        match="handoff_id is required",
    ):
        build_record(
            handoff_id=""
        )


@pytest.mark.parametrize(
    "handoff_id",
    [
        "abc",
        "g" * 32,
        "A" * 32,
        "a" * 31,
        "a" * 33,
    ],
)
def test_record_rejects_invalid_handoff_id(
    handoff_id: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="Invalid customer setup handoff_id",
    ):
        build_record(
            handoff_id=handoff_id
        )


def test_record_rejects_empty_verifier() -> None:
    with pytest.raises(
        ValueError,
        match="verifier_sha256 is required",
    ):
        build_record(
            verifier_sha256=""
        )


@pytest.mark.parametrize(
    "verifier",
    [
        "a" * 63,
        "a" * 65,
        "g" * 64,
    ],
)
def test_record_rejects_invalid_verifier(
    verifier: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Invalid customer setup handoff verifier"
        ),
    ):
        build_record(
            verifier_sha256=verifier
        )


def test_record_requires_status_enum() -> None:
    with pytest.raises(
        TypeError,
        match="CustomerSetupHandoffStatus",
    ):
        CustomerSetupHandoffRecord(
            issuance_request_id="request-001",
            handoff_id=HANDOFF_ID_A,
            setup_activation_id=(
                "setup-activation-001"
            ),
            verifier_sha256=VERIFIER_A,
            issued_at="2026-08-26T10:00:00Z",
            expires_at="2026-08-26T10:30:00Z",
            status="ACTIVE",
        )


@pytest.mark.parametrize(
    (
        "issued_at",
        "expires_at",
    ),
    [
        (
            "2026-08-26T10:00:00Z",
            "2026-08-26T10:00:00Z",
        ),
        (
            "2026-08-26T10:00:01Z",
            "2026-08-26T10:00:00Z",
        ),
    ],
)
def test_record_requires_expiration_after_issue(
    issued_at: str,
    expires_at: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "expires_at must be later than issued_at"
        ),
    ):
        build_record(
            issued_at=issued_at,
            expires_at=expires_at,
        )


def test_record_rejects_invalid_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match="issued_at must use ISO 8601 format",
    ):
        build_record(
            issued_at="not-a-timestamp"
        )


def test_issuance_result_redacts_plaintext_from_repr() -> None:
    result = CustomerSetupHandoffIssuanceResult(
        issuance_request_id="request-001",
        handoff_id=HANDOFF_ID_A,
        setup_activation_id=(
            "setup-activation-001"
        ),
        issued_at="2026-08-26T10:00:00Z",
        expires_at="2026-08-26T10:30:00Z",
        handoff_credential=(
            f"tdbsh1.{HANDOFF_ID_A}."
            "super-secret-material"
        ),
    )

    representation = repr(
        result
    )

    assert "super-secret-material" not in representation
    assert "handoff_credential" not in representation


def test_authorization_context_contains_no_secret() -> None:
    authorization = CustomerSetupHandoffAuthorization(
        handoff_id=HANDOFF_ID_A,
        setup_activation_id=(
            "setup-activation-001"
        ),
        customer_id="customer-001",
        deployment_id=None,
    )

    assert authorization.handoff_id == HANDOFF_ID_A
    assert authorization.customer_id == "customer-001"
    assert authorization.deployment_id is None

    assert not hasattr(
        authorization,
        "handoff_credential",
    )
    assert not hasattr(
        authorization,
        "verifier_sha256",
    )


def test_verifier_derivation_is_sha256() -> None:
    credential = (
        f"tdbsh1.{HANDOFF_ID_A}."
        "test-secret-material"
    )

    expected = hashlib.sha256(
        credential.encode(
            "utf-8"
        )
    ).hexdigest()

    assert (
        derive_customer_setup_handoff_verifier(
            credential
        )
        == expected
    )


def test_verifier_derivation_normalizes_outer_whitespace() -> None:
    credential = (
        f"tdbsh1.{HANDOFF_ID_A}."
        "test-secret-material"
    )

    assert (
        derive_customer_setup_handoff_verifier(
            f"  {credential}  "
        )
        == derive_customer_setup_handoff_verifier(
            credential
        )
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
    ],
)
def test_verifier_derivation_rejects_empty(
    value: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="handoff_credential is required",
    ):
        derive_customer_setup_handoff_verifier(
            value
        )


def test_store_requires_path() -> None:
    with pytest.raises(
        TypeError,
        match="storage_path must be Path",
    ):
        CustomerSetupHandoffStore(
            "handoffs.json",
        )


def test_store_requires_explicit_initialization(
    tmp_path: Path,
) -> None:
    store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )

    assert not store.is_ready()

    with pytest.raises(
        RuntimeError,
        match=(
            "Customer setup handoff store is not "
            "initialized"
        ),
    ):
        store.size()


def test_initialize_empty_creates_exact_payload(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "nested"
        / "handoffs.json"
    )

    store = CustomerSetupHandoffStore(
        path
    )
    store.initialize_empty()

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    assert payload == {
        "records": [],
        "version": 1,
    }


def test_store_supersede_registers_active_record(
    tmp_path: Path,
) -> None:
    store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    store.initialize_empty()

    record = build_record()

    assert store.supersede(record) == record
    assert store.size() == 1

    assert (
        store.get(
            handoff_id=HANDOFF_ID_A
        )
        == record
    )

    assert (
        store.get_by_issuance_request_id(
            issuance_request_id=(
                "handoff-request-001"
            )
        )
        == record
    )

    assert (
        store.get_by_verifier(
            verifier_sha256=VERIFIER_A
        )
        == record
    )

    assert (
        store.get_active_for_setup_activation(
            setup_activation_id=(
                "setup-activation-001"
            )
        )
        == record
    )


def test_new_handoff_revokes_old_active_for_same_activation(
    tmp_path: Path,
) -> None:
    store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    store.initialize_empty()

    first = build_record()

    second = build_record(
        issuance_request_id=(
            "handoff-request-002"
        ),
        handoff_id=HANDOFF_ID_B,
        verifier_sha256=VERIFIER_B,
    )

    store.supersede(
        first
    )

    store.supersede(
        second
    )

    stored_first = store.get(
        handoff_id=HANDOFF_ID_A
    )

    assert stored_first is not None
    assert (
        stored_first.status
        is CustomerSetupHandoffStatus.REVOKED
    )

    assert (
        store.get_active_for_setup_activation(
            setup_activation_id=(
                "setup-activation-001"
            )
        )
        == second
    )


def test_different_activations_may_have_active_handoffs(
    tmp_path: Path,
) -> None:
    store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    store.initialize_empty()

    first = build_record()

    second = build_record(
        issuance_request_id="request-002",
        handoff_id=HANDOFF_ID_B,
        setup_activation_id=(
            "setup-activation-002"
        ),
        verifier_sha256=VERIFIER_B,
    )

    store.supersede(
        first
    )
    store.supersede(
        second
    )

    assert store.size() == 2

    assert (
        store.get_active_for_setup_activation(
            setup_activation_id=(
                "setup-activation-001"
            )
        )
        == first
    )

    assert (
        store.get_active_for_setup_activation(
            setup_activation_id=(
                "setup-activation-002"
            )
        )
        == second
    )


def test_store_rejects_duplicate_handoff_id(
    tmp_path: Path,
) -> None:
    store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    store.initialize_empty()

    store.supersede(
        build_record()
    )

    with pytest.raises(
        ValueError,
        match="handoff_id is already assigned",
    ):
        store.supersede(
            build_record(
                issuance_request_id="request-002",
                verifier_sha256=VERIFIER_B,
            )
        )


def test_store_rejects_duplicate_issuance_request(
    tmp_path: Path,
) -> None:
    store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    store.initialize_empty()

    store.supersede(
        build_record()
    )

    with pytest.raises(
        ValueError,
        match="issuance request is already assigned",
    ):
        store.supersede(
            build_record(
                handoff_id=HANDOFF_ID_B,
                verifier_sha256=VERIFIER_B,
            )
        )


def test_store_rejects_duplicate_verifier(
    tmp_path: Path,
) -> None:
    store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    store.initialize_empty()

    store.supersede(
        build_record()
    )

    with pytest.raises(
        ValueError,
        match="verifier is already assigned",
    ):
        store.supersede(
            build_record(
                issuance_request_id="request-002",
                handoff_id=HANDOFF_ID_B,
                setup_activation_id=(
                    "setup-activation-002"
                ),
            )
        )


def test_new_handoff_must_start_active(
    tmp_path: Path,
) -> None:
    store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    store.initialize_empty()

    with pytest.raises(
        ValueError,
        match="must start ACTIVE",
    ):
        store.supersede(
            build_record(
                status=(
                    CustomerSetupHandoffStatus.REVOKED
                )
            )
        )


def test_rotate_verifier_preserves_identity_and_lifetime(
    tmp_path: Path,
) -> None:
    store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    store.initialize_empty()

    original = store.supersede(
        build_record()
    )

    updated = store.rotate_verifier(
        handoff_id=HANDOFF_ID_A,
        verifier_sha256=VERIFIER_B,
    )

    assert (
        updated.issuance_request_id
        == original.issuance_request_id
    )
    assert updated.handoff_id == original.handoff_id
    assert (
        updated.setup_activation_id
        == original.setup_activation_id
    )
    assert updated.issued_at == original.issued_at
    assert updated.expires_at == original.expires_at
    assert updated.verifier_sha256 == VERIFIER_B


def test_revoked_handoff_cannot_rotate_verifier(
    tmp_path: Path,
) -> None:
    store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    store.initialize_empty()

    store.supersede(
        build_record()
    )

    store.revoke(
        handoff_id=HANDOFF_ID_A
    )

    with pytest.raises(
        ValueError,
        match="REVOKED",
    ):
        store.rotate_verifier(
            handoff_id=HANDOFF_ID_A,
            verifier_sha256=VERIFIER_B,
        )


def test_revoke_is_idempotent_and_removes_active_index(
    tmp_path: Path,
) -> None:
    store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    store.initialize_empty()

    store.supersede(
        build_record()
    )

    first = store.revoke(
        handoff_id=HANDOFF_ID_A
    )

    second = store.revoke(
        handoff_id=HANDOFF_ID_A
    )

    assert second == first
    assert (
        first.status
        is CustomerSetupHandoffStatus.REVOKED
    )

    assert (
        store.get_active_for_setup_activation(
            setup_activation_id=(
                "setup-activation-001"
            )
        )
        is None
    )


def test_store_write_failure_does_not_install_new_handoff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    store.initialize_empty()

    def fail_write(
        records: object,
    ) -> None:
        raise RuntimeError(
            "simulated handoff write failure"
        )

    monkeypatch.setattr(
        store,
        "_write_records",
        fail_write,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated handoff write failure",
    ):
        store.supersede(
            build_record()
        )

    assert store.size() == 0
    assert (
        store.get(
            handoff_id=HANDOFF_ID_A
        )
        is None
    )


def test_store_write_failure_does_not_rotate_ram_verifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    store.initialize_empty()

    original = store.supersede(
        build_record()
    )

    def fail_write(
        records: object,
    ) -> None:
        raise RuntimeError(
            "simulated verifier write failure"
        )

    monkeypatch.setattr(
        store,
        "_write_records",
        fail_write,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated verifier write failure",
    ):
        store.rotate_verifier(
            handoff_id=HANDOFF_ID_A,
            verifier_sha256=VERIFIER_B,
        )

    stored = store.get(
        handoff_id=HANDOFF_ID_A
    )

    assert stored == original
    assert stored is not None
    assert stored.verifier_sha256 == VERIFIER_A


def test_store_write_failure_does_not_revoke_ram_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    store.initialize_empty()

    original = store.supersede(
        build_record()
    )

    def fail_write(
        records: object,
    ) -> None:
        raise RuntimeError(
            "simulated revoke write failure"
        )

    monkeypatch.setattr(
        store,
        "_write_records",
        fail_write,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated revoke write failure",
    ):
        store.revoke(
            handoff_id=HANDOFF_ID_A
        )

    assert (
        store.get(
            handoff_id=HANDOFF_ID_A
        )
        == original
    )


def test_restart_restores_indexes(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "handoffs.json"
    )

    store = CustomerSetupHandoffStore(
        path
    )
    store.initialize_empty()

    first = store.supersede(
        build_record()
    )

    second = store.supersede(
        build_record(
            issuance_request_id="request-002",
            handoff_id=HANDOFF_ID_B,
            setup_activation_id=(
                "setup-activation-002"
            ),
            verifier_sha256=VERIFIER_B,
        )
    )

    store.revoke(
        handoff_id=first.handoff_id
    )

    restarted = CustomerSetupHandoffStore(
        path
    )

    assert restarted.is_ready()
    assert restarted.size() == 2

    assert (
        restarted.get_by_issuance_request_id(
            issuance_request_id="request-002"
        )
        == second
    )

    assert (
        restarted.get_by_verifier(
            verifier_sha256=VERIFIER_B
        )
        == second
    )

    assert (
        restarted.get_active_for_setup_activation(
            setup_activation_id=(
                "setup-activation-002"
            )
        )
        == second
    )

    assert (
        restarted.get_active_for_setup_activation(
            setup_activation_id=(
                "setup-activation-001"
            )
        )
        is None
    )


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {
            "version": 999,
            "records": [],
        },
        {
            "version": 1,
            "records": "invalid",
        },
        {
            "version": 1,
            "records": [],
            "extra": True,
        },
        {
            "version": 1,
            "records": [
                "invalid",
            ],
        },
        {
            "version": 1,
            "records": [
                {
                    "issuance_request_id": "request-001",
                    "handoff_id": HANDOFF_ID_A,
                    "setup_activation_id": (
                        "setup-activation-001"
                    ),
                    "verifier_sha256": VERIFIER_A,
                    "issued_at": (
                        "2026-08-26T10:00:00Z"
                    ),
                    "expires_at": (
                        "2026-08-26T10:30:00Z"
                    ),
                    "status": "INVALID",
                }
            ],
        },
    ],
)
def test_store_rejects_malformed_payload(
    tmp_path: Path,
    payload: object,
) -> None:
    path = (
        tmp_path
        / "handoffs.json"
    )

    path.write_text(
        json.dumps(
            payload
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        (
            TypeError,
            ValueError,
        )
    ):
        CustomerSetupHandoffStore(
            path
        )


def test_restore_rejects_duplicate_handoff_id(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "handoffs.json"
    )

    record = {
        "issuance_request_id": "request-001",
        "handoff_id": HANDOFF_ID_A,
        "setup_activation_id": (
            "setup-activation-001"
        ),
        "verifier_sha256": VERIFIER_A,
        "issued_at": "2026-08-26T10:00:00Z",
        "expires_at": "2026-08-26T10:30:00Z",
        "status": "ACTIVE",
    }

    second = dict(
        record
    )
    second[
        "issuance_request_id"
    ] = "request-002"
    second[
        "verifier_sha256"
    ] = VERIFIER_B

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    record,
                    second,
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate customer setup handoff_id",
    ):
        CustomerSetupHandoffStore(
            path
        )


def test_restore_rejects_duplicate_issuance_request(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "handoffs.json"
    )

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    {
                        "issuance_request_id": "request-001",
                        "handoff_id": HANDOFF_ID_A,
                        "setup_activation_id": (
                            "setup-activation-001"
                        ),
                        "verifier_sha256": VERIFIER_A,
                        "issued_at": (
                            "2026-08-26T10:00:00Z"
                        ),
                        "expires_at": (
                            "2026-08-26T10:30:00Z"
                        ),
                        "status": "ACTIVE",
                    },
                    {
                        "issuance_request_id": "request-001",
                        "handoff_id": HANDOFF_ID_B,
                        "setup_activation_id": (
                            "setup-activation-002"
                        ),
                        "verifier_sha256": VERIFIER_B,
                        "issued_at": (
                            "2026-08-26T10:00:00Z"
                        ),
                        "expires_at": (
                            "2026-08-26T10:30:00Z"
                        ),
                        "status": "ACTIVE",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate customer setup handoff issuance",
    ):
        CustomerSetupHandoffStore(
            path
        )


def test_restore_rejects_duplicate_verifier(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "handoffs.json"
    )

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    {
                        "issuance_request_id": "request-001",
                        "handoff_id": HANDOFF_ID_A,
                        "setup_activation_id": (
                            "setup-activation-001"
                        ),
                        "verifier_sha256": VERIFIER_A,
                        "issued_at": (
                            "2026-08-26T10:00:00Z"
                        ),
                        "expires_at": (
                            "2026-08-26T10:30:00Z"
                        ),
                        "status": "ACTIVE",
                    },
                    {
                        "issuance_request_id": "request-002",
                        "handoff_id": HANDOFF_ID_B,
                        "setup_activation_id": (
                            "setup-activation-002"
                        ),
                        "verifier_sha256": VERIFIER_A,
                        "issued_at": (
                            "2026-08-26T10:00:00Z"
                        ),
                        "expires_at": (
                            "2026-08-26T10:30:00Z"
                        ),
                        "status": "ACTIVE",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate customer setup handoff verifier",
    ):
        CustomerSetupHandoffStore(
            path
        )


def test_restore_rejects_multiple_active_handoffs_for_activation(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "handoffs.json"
    )

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    {
                        "issuance_request_id": "request-001",
                        "handoff_id": HANDOFF_ID_A,
                        "setup_activation_id": (
                            "setup-activation-001"
                        ),
                        "verifier_sha256": VERIFIER_A,
                        "issued_at": (
                            "2026-08-26T10:00:00Z"
                        ),
                        "expires_at": (
                            "2026-08-26T10:30:00Z"
                        ),
                        "status": "ACTIVE",
                    },
                    {
                        "issuance_request_id": "request-002",
                        "handoff_id": HANDOFF_ID_B,
                        "setup_activation_id": (
                            "setup-activation-001"
                        ),
                        "verifier_sha256": VERIFIER_B,
                        "issued_at": (
                            "2026-08-26T10:00:00Z"
                        ),
                        "expires_at": (
                            "2026-08-26T10:30:00Z"
                        ),
                        "status": "ACTIVE",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Multiple ACTIVE customer setup handoffs",
    ):
        CustomerSetupHandoffStore(
            path
        )


def test_service_requires_correct_owner_types(
    tmp_path: Path,
) -> None:
    activation_store = CustomerSetupActivationStore(
        tmp_path
        / "activations.json"
    )
    activation_store.initialize_empty()

    handoff_store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    handoff_store.initialize_empty()

    with pytest.raises(
        TypeError,
        match="handoff_store",
    ):
        CustomerSetupHandoffService(
            handoff_store=object(),
            setup_activation_store=activation_store,
        )

    with pytest.raises(
        TypeError,
        match="setup_activation_store",
    ):
        CustomerSetupHandoffService(
            handoff_store=handoff_store,
            setup_activation_store=object(),
        )


def test_service_requires_ready_sources(
    tmp_path: Path,
) -> None:
    activation_store = CustomerSetupActivationStore(
        tmp_path
        / "activations.json"
    )
    activation_store.initialize_empty()

    unready_handoff = CustomerSetupHandoffStore(
        tmp_path
        / "unready-handoffs.json"
    )

    with pytest.raises(
        RuntimeError,
        match="handoff store",
    ):
        CustomerSetupHandoffService(
            handoff_store=unready_handoff,
            setup_activation_store=activation_store,
        )

    handoff_store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    handoff_store.initialize_empty()

    unready_activation = CustomerSetupActivationStore(
        tmp_path
        / "unready-activations.json"
    )

    with pytest.raises(
        RuntimeError,
        match="activation store",
    ):
        CustomerSetupHandoffService(
            handoff_store=handoff_store,
            setup_activation_store=unready_activation,
        )


def test_issue_requires_existing_setup_activation(
    tmp_path: Path,
) -> None:
    _, handoff_store, service = build_environment(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="Unknown customer setup activation",
    ):
        service.issue(
            issuance_request_id="request-001",
            setup_activation_id=(
                "setup-activation-missing"
            ),
            current_time=NOW,
        )

    assert handoff_store.size() == 0


def test_issue_active_setup_activation(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        handoff_store,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    result = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    assert result.handoff_id
    assert len(
        result.handoff_id
    ) == 32

    assert result.handoff_credential.startswith(
        f"tdbsh1.{result.handoff_id}."
    )

    assert (
        result.issued_at
        == "2026-08-26T10:00:00Z"
    )

    assert (
        result.expires_at
        == "2026-08-26T10:30:00Z"
    )

    assert handoff_store.size() == 1


def test_handoff_lifetime_is_exactly_thirty_minutes(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    result = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    issued = datetime.fromisoformat(
        result.issued_at.replace(
            "Z",
            "+00:00",
        )
    )

    expires = datetime.fromisoformat(
        result.expires_at.replace(
            "Z",
            "+00:00",
        )
    )

    assert (
        expires - issued
        == timedelta(
            minutes=30
        )
    )


def test_naive_issue_time_is_treated_as_utc(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    result = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=datetime(
            2026,
            8,
            26,
            10,
            0,
            0,
        ),
    )

    assert (
        result.issued_at
        == "2026-08-26T10:00:00Z"
    )


def test_bound_setup_activation_may_receive_handoff(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_bound_activation(
        activation_store
    )

    result = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    assert result.handoff_credential


def test_suspended_setup_activation_cannot_receive_handoff(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        handoff_store,
        service,
    ) = build_environment(
        tmp_path
    )

    create_suspended_activation(
        activation_store
    )

    with pytest.raises(
        ValueError,
        match="SUSPENDED",
    ):
        service.issue(
            issuance_request_id="request-001",
            setup_activation_id=(
                "setup-activation-001"
            ),
            current_time=NOW,
        )

    assert handoff_store.size() == 0


def test_issue_retry_keeps_identity_and_lifetime_but_rotates_secret(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        handoff_store,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    first = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    first_record = handoff_store.get(
        handoff_id=first.handoff_id
    )

    assert first_record is not None

    second = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=10
            )
        ),
    )

    second_record = handoff_store.get(
        handoff_id=second.handoff_id
    )

    assert second_record is not None

    assert second.handoff_id == first.handoff_id
    assert second.issued_at == first.issued_at
    assert second.expires_at == first.expires_at

    assert (
        second.handoff_credential
        != first.handoff_credential
    )

    assert (
        second_record.verifier_sha256
        != first_record.verifier_sha256
    )

    assert handoff_store.size() == 1


def test_issue_retry_does_not_extend_ttl(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    first = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    second = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=29
            )
        ),
    )

    assert second.issued_at == first.issued_at
    assert second.expires_at == first.expires_at


def test_old_credential_fails_after_retry_rotation(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    first = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    second = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=1
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="Invalid customer setup handoff credential",
    ):
        service.authorize(
            handoff_credential=(
                first.handoff_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=2
                )
            ),
        )

    authorization = service.authorize(
        handoff_credential=(
            second.handoff_credential
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=2
            )
        ),
    )

    assert (
        authorization.setup_activation_id
        == "setup-activation-001"
    )


def test_issue_request_cannot_move_to_other_activation(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store,
        setup_activation_id=(
            "setup-activation-001"
        ),
    )

    create_active_activation(
        activation_store,
        request_id="activation-request-002",
        setup_activation_id=(
            "setup-activation-002"
        ),
    )

    service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    with pytest.raises(
        ValueError,
        match="different setup activation",
    ):
        service.issue(
            issuance_request_id="request-001",
            setup_activation_id=(
                "setup-activation-002"
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_expired_handoff_cannot_be_reissued_at_boundary(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    with pytest.raises(
        ValueError,
        match="Expired customer setup handoff",
    ):
        service.issue(
            issuance_request_id="request-001",
            setup_activation_id=(
                "setup-activation-001"
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=30
                )
            ),
        )


def test_revoked_handoff_cannot_be_reissued(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    service.revoke(
        handoff_id=issued.handoff_id
    )

    with pytest.raises(
        ValueError,
        match="REVOKED customer setup handoff",
    ):
        service.issue(
            issuance_request_id="request-001",
            setup_activation_id=(
                "setup-activation-001"
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_new_issuance_request_supersedes_previous_handoff(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        handoff_store,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    first = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    second = service.issue(
        issuance_request_id="request-002",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=1
            )
        ),
    )

    assert second.handoff_id != first.handoff_id

    first_record = handoff_store.get(
        handoff_id=first.handoff_id
    )

    assert first_record is not None
    assert (
        first_record.status
        is CustomerSetupHandoffStatus.REVOKED
    )

    assert (
        handoff_store
        .get_active_for_setup_activation(
            setup_activation_id=(
                "setup-activation-001"
            )
        )
        .handoff_id
        == second.handoff_id
    )

    with pytest.raises(
        ValueError,
        match="revoked",
    ):
        service.authorize(
            handoff_credential=(
                first.handoff_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=2
                )
            ),
        )


def test_new_request_after_old_expiry_is_allowed(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        handoff_store,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    first = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    second = service.issue(
        issuance_request_id="request-002",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=31
            )
        ),
    )

    assert second.handoff_id != first.handoff_id

    first_record = handoff_store.get(
        handoff_id=first.handoff_id
    )

    assert first_record is not None
    assert (
        first_record.status
        is CustomerSetupHandoffStatus.REVOKED
    )


def test_authorize_valid_active_handoff(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    authorization = service.authorize(
        handoff_credential=(
            issued.handoff_credential
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=1
            )
        ),
    )

    assert (
        authorization.handoff_id
        == issued.handoff_id
    )
    assert (
        authorization.setup_activation_id
        == "setup-activation-001"
    )
    assert authorization.customer_id == "customer-001"
    assert authorization.deployment_id is None


def test_authorize_accepts_outer_whitespace(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    authorization = service.authorize(
        handoff_credential=(
            f"  {issued.handoff_credential}  "
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=1
            )
        ),
    )

    assert (
        authorization.handoff_id
        == issued.handoff_id
    )


@pytest.mark.parametrize(
    "credential",
    [
        "",
        "wrong",
        "tdbsh1.only-two",
        "wrongprefix."
        + HANDOFF_ID_A
        + "."
        + ("x" * 40),
        "tdbsh1.invalid-id."
        + ("x" * 40),
        "tdbsh1."
        + HANDOFF_ID_A
        + ".short",
        "tdbsh1."
        + HANDOFF_ID_A
        + "."
        + ("!" * 40),
    ],
)
def test_authorize_rejects_malformed_credential(
    tmp_path: Path,
    credential: str,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    with pytest.raises(
        ValueError,
        match="Invalid customer setup handoff credential",
    ):
        service.authorize(
            handoff_credential=credential,
            current_time=NOW,
        )


def test_authorize_rejects_unknown_handoff_id(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    credential = (
        f"tdbsh1.{HANDOFF_ID_A}."
        + ("x" * 43)
    )

    with pytest.raises(
        ValueError,
        match="Invalid customer setup handoff credential",
    ):
        service.authorize(
            handoff_credential=credential,
            current_time=NOW,
        )


def test_authorize_rejects_wrong_secret(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    wrong = (
        f"tdbsh1.{issued.handoff_id}."
        + ("x" * 43)
    )

    with pytest.raises(
        ValueError,
        match="Invalid customer setup handoff credential",
    ):
        service.authorize(
            handoff_credential=wrong,
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_verifier_comparison_uses_compare_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    original = (
        handoff_module.compare_digest
    )

    calls = []

    def recording_compare_digest(
        left: str,
        right: str,
    ) -> bool:
        calls.append(
            (
                left,
                right,
            )
        )

        return original(
            left,
            right,
        )

    monkeypatch.setattr(
        handoff_module,
        "compare_digest",
        recording_compare_digest,
    )

    service.authorize(
        handoff_credential=(
            issued.handoff_credential
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=1
            )
        ),
    )

    assert len(
        calls
    ) == 1


def test_compare_digest_result_is_authoritative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    monkeypatch.setattr(
        handoff_module,
        "compare_digest",
        lambda left, right: False,
    )

    with pytest.raises(
        ValueError,
        match="Invalid customer setup handoff credential",
    ):
        service.authorize(
            handoff_credential=(
                issued.handoff_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_authorize_before_expiry_boundary_succeeds(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    authorization = service.authorize(
        handoff_credential=(
            issued.handoff_credential
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=30
            )
            - timedelta(
                microseconds=1
            )
        ),
    )

    assert (
        authorization.handoff_id
        == issued.handoff_id
    )


def test_authorize_expires_exactly_at_boundary(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    with pytest.raises(
        ValueError,
        match="credential is expired",
    ):
        service.authorize(
            handoff_credential=(
                issued.handoff_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=30
                )
            ),
        )


def test_authorize_rejects_revoked_handoff(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    service.revoke(
        handoff_id=issued.handoff_id
    )

    with pytest.raises(
        ValueError,
        match="credential is revoked",
    ):
        service.authorize(
            handoff_credential=(
                issued.handoff_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_activation_suspension_invalidates_existing_handoff(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    activation = create_active_activation(
        activation_store
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            activation.setup_activation_id
        ),
        current_time=NOW,
    )

    activation_store.suspend(
        setup_activation_id=(
            activation.setup_activation_id
        )
    )

    with pytest.raises(
        ValueError,
        match="SUSPENDED",
    ):
        service.authorize(
            handoff_credential=(
                issued.handoff_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_bound_activation_authorization_returns_deployment(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_bound_activation(
        activation_store,
        deployment_id="deployment-001",
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    authorization = service.authorize(
        handoff_credential=(
            issued.handoff_credential
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=1
            )
        ),
    )

    assert (
        authorization.deployment_id
        == "deployment-001"
    )


def test_active_activation_authorization_has_no_deployment(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    authorization = service.authorize(
        handoff_credential=(
            issued.handoff_credential
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=1
            )
        ),
    )

    assert authorization.deployment_id is None


def test_restart_recovers_valid_handoff(
    tmp_path: Path,
) -> None:
    activation_path = (
        tmp_path
        / "activations.json"
    )

    handoff_path = (
        tmp_path
        / "handoffs.json"
    )

    activations = CustomerSetupActivationStore(
        activation_path
    )
    activations.initialize_empty()

    create_active_activation(
        activations
    )

    handoffs = CustomerSetupHandoffStore(
        handoff_path
    )
    handoffs.initialize_empty()

    service = CustomerSetupHandoffService(
        handoff_store=handoffs,
        setup_activation_store=activations,
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    restarted_service = CustomerSetupHandoffService(
        handoff_store=(
            CustomerSetupHandoffStore(
                handoff_path
            )
        ),
        setup_activation_store=(
            CustomerSetupActivationStore(
                activation_path
            )
        ),
    )

    authorization = restarted_service.authorize(
        handoff_credential=(
            issued.handoff_credential
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=1
            )
        ),
    )

    assert (
        authorization.handoff_id
        == issued.handoff_id
    )


def test_service_restore_rejects_orphaned_activation_reference(
    tmp_path: Path,
) -> None:
    activation_store = CustomerSetupActivationStore(
        tmp_path
        / "activations.json"
    )
    activation_store.initialize_empty()

    handoff_store = CustomerSetupHandoffStore(
        tmp_path
        / "handoffs.json"
    )
    handoff_store.initialize_empty()

    handoff_store.supersede(
        build_record(
            setup_activation_id=(
                "setup-activation-missing"
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match="unknown setup activation",
    ):
        CustomerSetupHandoffService(
            handoff_store=handoff_store,
            setup_activation_store=activation_store,
        )


def test_service_restart_allows_handoff_whose_activation_is_suspended(
    tmp_path: Path,
) -> None:
    activation_path = (
        tmp_path
        / "activations.json"
    )

    handoff_path = (
        tmp_path
        / "handoffs.json"
    )

    activations = CustomerSetupActivationStore(
        activation_path
    )
    activations.initialize_empty()

    activation = create_active_activation(
        activations
    )

    handoffs = CustomerSetupHandoffStore(
        handoff_path
    )
    handoffs.initialize_empty()

    service = CustomerSetupHandoffService(
        handoff_store=handoffs,
        setup_activation_store=activations,
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            activation.setup_activation_id
        ),
        current_time=NOW,
    )

    activations.suspend(
        setup_activation_id=(
            activation.setup_activation_id
        )
    )

    restarted_service = CustomerSetupHandoffService(
        handoff_store=(
            CustomerSetupHandoffStore(
                handoff_path
            )
        ),
        setup_activation_store=(
            CustomerSetupActivationStore(
                activation_path
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="SUSPENDED",
    ):
        restarted_service.authorize(
            handoff_credential=(
                issued.handoff_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_persistence_contains_only_owned_handoff_truth(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        handoff_store,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    issued = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    payload = json.loads(
        handoff_store.storage_path.read_text(
            encoding="utf-8",
        )
    )

    assert set(
        payload
    ) == {
        "version",
        "records",
    }

    assert len(
        payload["records"]
    ) == 1

    record = payload[
        "records"
    ][0]

    assert set(
        record
    ) == {
        "issuance_request_id",
        "handoff_id",
        "setup_activation_id",
        "verifier_sha256",
        "issued_at",
        "expires_at",
        "status",
    }

    serialized = json.dumps(
        payload
    )

    assert (
        issued.handoff_credential
        not in serialized
    )

    secret = (
        issued.handoff_credential
        .split(
            ".",
            2,
        )[2]
    )

    assert secret not in serialized

    forbidden_fields = {
        "customer_id",
        "deployment_id",
        "payment_id",
        "transaction_id",
        "subscription_id",
        "amount",
        "currency",
        "email",
        "phone",
        "password",
        "account_fingerprint",
        "agent_id",
        "credential_id",
        "access_credential",
        "package_path",
        "package_root",
        "entitlement",
    }

    assert forbidden_fields.isdisjoint(
        record
    )


def test_expiration_is_not_durable_status() -> None:
    assert {
        item.value
        for item in CustomerSetupHandoffStatus
    } == {
        "ACTIVE",
        "REVOKED",
    }

    assert "EXPIRED" not in {
        item.value
        for item in CustomerSetupHandoffStatus
    }


def test_issue_contract_accepts_only_handoff_scope_inputs() -> None:
    parameters = inspect.signature(
        CustomerSetupHandoffService.issue
    ).parameters

    assert tuple(
        parameters
    ) == (
        "self",
        "issuance_request_id",
        "setup_activation_id",
        "current_time",
    )

    forbidden = {
        "customer_id",
        "deployment_id",
        "payment_id",
        "transaction_id",
        "subscription_id",
        "account_fingerprint",
        "agent_id",
        "credential",
        "package",
        "entitlement",
        "ttl",
        "expires_at",
    }

    assert forbidden.isdisjoint(
        parameters
    )


def test_authorize_contract_accepts_only_credential_and_time() -> None:
    parameters = inspect.signature(
        CustomerSetupHandoffService.authorize
    ).parameters

    assert tuple(
        parameters
    ) == (
        "self",
        "handoff_credential",
        "current_time",
    )


def test_current_time_type_is_enforced(
    tmp_path: Path,
) -> None:
    (
        activation_store,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    with pytest.raises(
        TypeError,
        match="current_time must be datetime",
    ):
        service.issue(
            issuance_request_id="request-001",
            setup_activation_id=(
                "setup-activation-001"
            ),
            current_time="2026-08-26T10:00:00Z",
        )


def test_handoff_id_collision_is_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        activation_store,
        handoff_store,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    create_active_activation(
        activation_store,
        request_id="activation-request-002",
        setup_activation_id=(
            "setup-activation-002"
        ),
        customer_id="customer-002",
    )

    handoff_store.supersede(
        build_record(
            setup_activation_id=(
                "setup-activation-002"
            )
        )
    )

    ids = iter(
        [
            HANDOFF_ID_A,
            HANDOFF_ID_B,
        ]
    )

    monkeypatch.setattr(
        handoff_module.secrets,
        "token_hex",
        lambda count: next(
            ids
        ),
    )

    monkeypatch.setattr(
        handoff_module.secrets,
        "token_urlsafe",
        lambda count: (
            "unique-secret-material-for-handoff-001"
        ),
    )

    issued = service.issue(
        issuance_request_id="request-new",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    assert issued.handoff_id == HANDOFF_ID_B


def test_generation_failure_is_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        activation_store,
        handoff_store,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    create_active_activation(
        activation_store,
        request_id="activation-request-002",
        setup_activation_id=(
            "setup-activation-002"
        ),
        customer_id="customer-002",
    )

    handoff_store.supersede(
        build_record(
            setup_activation_id=(
                "setup-activation-002"
            )
        )
    )

    monkeypatch.setattr(
        handoff_module.secrets,
        "token_hex",
        lambda count: HANDOFF_ID_A,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Unable to generate unique customer setup "
            "handoff credential"
        ),
    ):
        service.issue(
            issuance_request_id="request-new",
            setup_activation_id=(
                "setup-activation-001"
            ),
            current_time=NOW,
        )


def test_new_issuance_write_failure_does_not_revoke_old_handoff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        activation_store,
        handoff_store,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    first = service.issue(
        issuance_request_id="request-001",
        setup_activation_id=(
            "setup-activation-001"
        ),
        current_time=NOW,
    )

    original = handoff_store.get(
        handoff_id=first.handoff_id
    )

    assert original is not None

    def fail_write(
        records: object,
    ) -> None:
        raise RuntimeError(
            "simulated supersede failure"
        )

    monkeypatch.setattr(
        handoff_store,
        "_write_records",
        fail_write,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated supersede failure",
    ):
        service.issue(
            issuance_request_id="request-002",
            setup_activation_id=(
                "setup-activation-001"
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )

    after = handoff_store.get(
        handoff_id=first.handoff_id
    )

    assert after == original
    assert (
        after.status
        is CustomerSetupHandoffStatus.ACTIVE
    )


def test_plaintext_is_returned_only_after_durable_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        activation_store,
        handoff_store,
        service,
    ) = build_environment(
        tmp_path
    )

    create_active_activation(
        activation_store
    )

    def fail_write(
        records: object,
    ) -> None:
        raise RuntimeError(
            "simulated persistence failure"
        )

    monkeypatch.setattr(
        handoff_store,
        "_write_records",
        fail_write,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated persistence failure",
    ):
        service.issue(
            issuance_request_id="request-001",
            setup_activation_id=(
                "setup-activation-001"
            ),
            current_time=NOW,
        )

    assert handoff_store.size() == 0


def test_revoke_unknown_handoff_fails_closed(
    tmp_path: Path,
) -> None:
    (
        _,
        _,
        service,
    ) = build_environment(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="Unknown customer setup handoff",
    ):
        service.revoke(
            handoff_id=HANDOFF_ID_A
        )