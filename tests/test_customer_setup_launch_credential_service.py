"""
Owner tests for TODOBA Customer Setup Launch Credential.
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import inspect
import json
from pathlib import Path

import pytest

from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)
from backend.commercial.customer_setup_launch_credential_service import (
    CustomerSetupLaunchAuthorization,
    CustomerSetupLaunchCredentialRecord,
    CustomerSetupLaunchCredentialService,
    CustomerSetupLaunchCredentialStatus,
    CustomerSetupLaunchCredentialStore,
    derive_customer_setup_launch_verifier,
)


NOW = datetime(
    2026,
    8,
    30,
    10,
    0,
    0,
    tzinfo=timezone.utc,
)


def _identity_registry(
    tmp_path: Path,
    *,
    customers=(
        "customer-001",
    ),
) -> CustomerIdentityRegistry:
    registry = CustomerIdentityRegistry(
        tmp_path
        / "customer_identities.json"
    )
    registry.initialize_empty()

    for customer_id in customers:
        registry.register(
            CustomerIdentity(
                customer_id=customer_id
            )
        )

    return registry


def _store(
    tmp_path: Path,
    identities: CustomerIdentityRegistry,
) -> CustomerSetupLaunchCredentialStore:
    store = (
        CustomerSetupLaunchCredentialStore(
            tmp_path
            / "customer_setup_launch_credentials.json",
            customer_identity_registry=(
                identities
            ),
        )
    )
    store.initialize_empty()
    return store


def _service(
    tmp_path: Path,
    *,
    customers=(
        "customer-001",
    ),
):
    identities = _identity_registry(
        tmp_path,
        customers=customers,
    )
    store = _store(
        tmp_path,
        identities,
    )
    service = (
        CustomerSetupLaunchCredentialService(
            launch_store=store,
            customer_identity_registry=(
                identities
            ),
        )
    )

    return (
        identities,
        store,
        service,
    )


def _issue(
    service: CustomerSetupLaunchCredentialService,
    *,
    request_id="launch-request-001",
    customer_id="customer-001",
    current_time=NOW,
):
    return service.issue(
        issuance_request_id=request_id,
        customer_id=customer_id,
        current_time=current_time,
    )


def test_issue_creates_short_lived_launch_credential(
    tmp_path: Path,
) -> None:
    _, store, service = _service(
        tmp_path
    )

    issued = _issue(
        service
    )

    assert (
        issued.issuance_request_id
        == "launch-request-001"
    )
    assert (
        issued.customer_id
        == "customer-001"
    )
    assert len(
        issued.launch_id
    ) == 32
    assert (
        issued.launch_credential.startswith(
            "tdbsl."
            + issued.launch_id
            + "."
        )
    )

    issued_at = datetime.fromisoformat(
        issued.issued_at.replace(
            "Z",
            "+00:00",
        )
    )
    expires_at = datetime.fromisoformat(
        issued.expires_at.replace(
            "Z",
            "+00:00",
        )
    )

    assert (
        expires_at
        - issued_at
        == timedelta(
            minutes=15
        )
    )

    record = store.get(
        launch_id=issued.launch_id
    )

    assert record is not None
    assert (
        record.status
        is CustomerSetupLaunchCredentialStatus
        .ACTIVE
    )


def test_plaintext_credential_is_never_persisted(
    tmp_path: Path,
) -> None:
    _, store, service = _service(
        tmp_path
    )

    issued = _issue(
        service
    )

    persisted = (
        store.storage_path.read_text(
            encoding="utf-8"
        )
    )

    secret = (
        issued.launch_credential.split(
            "."
        )[2]
    )

    assert (
        issued.launch_credential
        not in persisted
    )
    assert secret not in persisted
    assert (
        derive_customer_setup_launch_verifier(
            issued.launch_credential
        )
        in persisted
    )


def test_issuance_result_repr_redacts_plaintext(
    tmp_path: Path,
) -> None:
    _, _, service = _service(
        tmp_path
    )

    issued = _issue(
        service
    )

    rendered = repr(
        issued
    )

    assert (
        issued.launch_credential
        not in rendered
    )
    assert (
        "launch_credential=<redacted>"
        in rendered
    )


def test_authorize_returns_authoritative_customer(
    tmp_path: Path,
) -> None:
    _, _, service = _service(
        tmp_path
    )

    issued = _issue(
        service
    )

    authorized = service.authorize(
        launch_credential=(
            issued.launch_credential
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=1
            )
        ),
    )

    assert isinstance(
        authorized,
        CustomerSetupLaunchAuthorization,
    )
    assert (
        authorized.launch_id
        == issued.launch_id
    )
    assert (
        authorized.customer_id
        == "customer-001"
    )


def test_retry_rotates_secret_but_preserves_identity_and_lifetime(
    tmp_path: Path,
) -> None:
    _, store, service = _service(
        tmp_path
    )

    first = _issue(
        service
    )

    second = _issue(
        service,
        current_time=(
            NOW
            + timedelta(
                minutes=1
            )
        ),
    )

    assert (
        second.launch_id
        == first.launch_id
    )
    assert (
        second.customer_id
        == first.customer_id
    )
    assert (
        second.issued_at
        == first.issued_at
    )
    assert (
        second.expires_at
        == first.expires_at
    )
    assert (
        second.launch_credential
        != first.launch_credential
    )

    record = store.get(
        launch_id=first.launch_id
    )

    assert record is not None
    assert (
        record.verifier_sha256
        == derive_customer_setup_launch_verifier(
            second.launch_credential
        )
    )


def test_retry_invalidates_previous_plaintext(
    tmp_path: Path,
) -> None:
    _, _, service = _service(
        tmp_path
    )

    first = _issue(
        service
    )

    second = _issue(
        service,
        current_time=(
            NOW
            + timedelta(
                minutes=1
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="Invalid",
    ):
        service.authorize(
            launch_credential=(
                first.launch_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=2
                )
            ),
        )

    authorized = service.authorize(
        launch_credential=(
            second.launch_credential
        ),
        current_time=(
            NOW
            + timedelta(
                minutes=2
            )
        ),
    )

    assert (
        authorized.customer_id
        == "customer-001"
    )


def test_same_request_cannot_move_to_another_customer(
    tmp_path: Path,
) -> None:
    _, _, service = _service(
        tmp_path,
        customers=(
            "customer-001",
            "customer-002",
        ),
    )

    _issue(
        service
    )

    with pytest.raises(
        ValueError,
        match="another customer",
    ):
        _issue(
            service,
            customer_id="customer-002",
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_unknown_customer_cannot_receive_launch_credential(
    tmp_path: Path,
) -> None:
    _, _, service = _service(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="not authoritatively registered",
    ):
        _issue(
            service,
            customer_id="unknown-customer",
        )


def test_expired_credential_is_rejected(
    tmp_path: Path,
) -> None:
    _, _, service = _service(
        tmp_path
    )

    issued = _issue(
        service
    )

    with pytest.raises(
        ValueError,
        match="expired",
    ):
        service.authorize(
            launch_credential=(
                issued.launch_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=15
                )
            ),
        )


def test_expired_request_cannot_be_reissued(
    tmp_path: Path,
) -> None:
    _, _, service = _service(
        tmp_path
    )

    _issue(
        service
    )

    with pytest.raises(
        ValueError,
        match="Expired",
    ):
        _issue(
            service,
            current_time=(
                NOW
                + timedelta(
                    minutes=15
                )
            ),
        )


def test_revoke_invalidates_credential(
    tmp_path: Path,
) -> None:
    _, _, service = _service(
        tmp_path
    )

    issued = _issue(
        service
    )

    revoked = service.revoke(
        launch_id=issued.launch_id
    )

    assert (
        revoked.status
        is CustomerSetupLaunchCredentialStatus
        .REVOKED
    )

    with pytest.raises(
        ValueError,
        match="revoked",
    ):
        service.authorize(
            launch_credential=(
                issued.launch_credential
            ),
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_revoked_request_cannot_be_reissued(
    tmp_path: Path,
) -> None:
    _, _, service = _service(
        tmp_path
    )

    issued = _issue(
        service
    )

    service.revoke(
        launch_id=issued.launch_id
    )

    with pytest.raises(
        ValueError,
        match="REVOKED",
    ):
        _issue(
            service,
            current_time=(
                NOW
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_malformed_credential_is_rejected(
    tmp_path: Path,
) -> None:
    _, _, service = _service(
        tmp_path
    )

    for malformed in (
        "",
        "bad",
        "bad.prefix.value",
        "tdbsl.bad.secret",
    ):
        with pytest.raises(
            (
                ValueError,
                TypeError,
            )
        ):
            service.authorize(
                launch_credential=malformed,
                current_time=NOW,
            )


def test_unknown_launch_id_is_rejected(
    tmp_path: Path,
) -> None:
    _, _, service = _service(
        tmp_path
    )

    unknown = (
        "tdbsl."
        + ("a" * 32)
        + "."
        + ("B" * 40)
    )

    with pytest.raises(
        ValueError,
        match="Invalid",
    ):
        service.authorize(
            launch_credential=unknown,
            current_time=NOW,
        )


def test_naive_current_time_is_rejected(
    tmp_path: Path,
) -> None:
    _, _, service = _service(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        _issue(
            service,
            current_time=datetime(
                2026,
                8,
                30,
                10,
                0,
                0,
            ),
        )


def test_store_reopens_durable_state(
    tmp_path: Path,
) -> None:
    identities, store, service = _service(
        tmp_path
    )

    issued = _issue(
        service
    )

    reopened = (
        CustomerSetupLaunchCredentialStore(
            store.storage_path,
            customer_identity_registry=(
                identities
            ),
        )
    )
    reopened.open_existing()

    restored = reopened.get(
        launch_id=issued.launch_id
    )

    assert restored is not None
    assert (
        restored.customer_id
        == "customer-001"
    )
    assert (
        restored.verifier_sha256
        == derive_customer_setup_launch_verifier(
            issued.launch_credential
        )
    )


def test_store_restore_rejects_unknown_customer(
    tmp_path: Path,
) -> None:
    identities, store, service = _service(
        tmp_path
    )

    _issue(
        service
    )

    payload = json.loads(
        store.storage_path.read_text(
            encoding="utf-8"
        )
    )

    payload[
        "records"
    ][0][
        "customer_id"
    ] = "unknown-customer"

    store.storage_path.write_text(
        json.dumps(
            payload
        ),
        encoding="utf-8",
    )

    reopened = (
        CustomerSetupLaunchCredentialStore(
            store.storage_path,
            customer_identity_registry=(
                identities
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="unknown customer",
    ):
        reopened.open_existing()


def test_store_initialize_empty_never_overwrites_existing_file(
    tmp_path: Path,
) -> None:
    identities = _identity_registry(
        tmp_path
    )

    path = (
        tmp_path
        / "existing_launch_store.json"
    )
    path.write_text(
        "preserve-me",
        encoding="utf-8",
    )

    store = (
        CustomerSetupLaunchCredentialStore(
            path,
            customer_identity_registry=(
                identities
            ),
        )
    )

    with pytest.raises(
        FileExistsError,
    ):
        store.initialize_empty()

    assert (
        path.read_text(
            encoding="utf-8"
        )
        == "preserve-me"
    )


def test_store_requires_ready_before_reads(
    tmp_path: Path,
) -> None:
    identities = _identity_registry(
        tmp_path
    )

    store = (
        CustomerSetupLaunchCredentialStore(
            tmp_path
            / "not_initialized.json",
            customer_identity_registry=(
                identities
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        store.all()


def test_service_requires_ready_store(
    tmp_path: Path,
) -> None:
    identities = _identity_registry(
        tmp_path
    )

    store = (
        CustomerSetupLaunchCredentialStore(
            tmp_path
            / "not_initialized.json",
            customer_identity_registry=(
                identities
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
        match="store is not initialized",
    ):
        CustomerSetupLaunchCredentialService(
            launch_store=store,
            customer_identity_registry=(
                identities
            ),
        )


def test_record_contains_no_plaintext_secret_field() -> None:
    fields = {
        field_name
        for field_name in (
            CustomerSetupLaunchCredentialRecord
            .__dataclass_fields__
        )
    }

    assert fields == {
        "issuance_request_id",
        "launch_id",
        "customer_id",
        "verifier_sha256",
        "issued_at",
        "expires_at",
        "status",
    }


def test_issue_contract_is_pre_setup_customer_only() -> None:
    parameters = (
        inspect.signature(
            CustomerSetupLaunchCredentialService
            .issue
        ).parameters
    )

    assert set(
        parameters
    ) == {
        "self",
        "issuance_request_id",
        "customer_id",
        "current_time",
    }

    forbidden = {
        "deployment_id",
        "agent_id",
        "credential_id",
        "entitlement_id",
        "package_path",
    }

    assert forbidden.isdisjoint(
        parameters
    )


def test_owner_has_no_http_or_setup_entry_ownership() -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_launch_credential_service.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    forbidden_tokens = (
        "from fastapi",
        "import fastapi",
        "import httpx",
        "backend.main",
        "CustomerSetupEntryGrantService",
        "CustomerSetupHandoffService",
        "CustomerSetupActivationService",
        "CustomerSetupHttpClient",
        "MetaTrader5",
        "deployment_id",
        "agent_id",
    )

    for token in forbidden_tokens:
        assert token not in source