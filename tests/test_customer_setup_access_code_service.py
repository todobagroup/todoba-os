import inspect
import json
from pathlib import Path

import pytest

from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationRecord,
    CustomerSetupActivationStatus,
    CustomerSetupActivationStore,
)
from backend.commercial.customer_setup_access_code_service import (
    CustomerSetupAccessCodeService,
    CustomerSetupAccessCodeStatus,
    CustomerSetupAccessCodeStore,
)


_CUSTOMER_ID = "customer-001"
_ACTIVATION_ID = "setup-activation-001"


def _build_activation_store(
    tmp_path: Path,
) -> CustomerSetupActivationStore:
    store = CustomerSetupActivationStore(
        tmp_path
        / "customer_setup_activations.json"
    )
    store.initialize_empty()

    store.register(
        CustomerSetupActivationRecord(
            activation_request_id=(
                "activation-request-001"
            ),
            setup_activation_id=(
                _ACTIVATION_ID
            ),
            customer_id=_CUSTOMER_ID,
            status=(
                CustomerSetupActivationStatus.ACTIVE
            ),
        )
    )

    return store


def _build_service(
    tmp_path: Path,
):
    activation_store = (
        _build_activation_store(
            tmp_path
        )
    )

    access_store = (
        CustomerSetupAccessCodeStore(
            tmp_path
            / "customer_setup_access_codes.json",
            setup_activation_store=(
                activation_store
            ),
        )
    )
    access_store.initialize_empty()

    service = CustomerSetupAccessCodeService(
        access_code_store=access_store,
        setup_activation_store=(
            activation_store
        ),
    )

    return (
        activation_store,
        access_store,
        service,
    )


def test_issue_and_authorize_returns_authoritative_identity(
    tmp_path,
) -> None:
    _, _, service = _build_service(
        tmp_path
    )

    issued = service.issue(
        setup_activation_id=(
            _ACTIVATION_ID
        )
    )

    authorized = service.authorize(
        activation_code=(
            issued.activation_code
        )
    )

    assert (
        authorized.setup_activation_id
        == _ACTIVATION_ID
    )
    assert authorized.customer_id == _CUSTOMER_ID


def test_plaintext_activation_code_is_not_persisted(
    tmp_path,
) -> None:
    _, access_store, service = (
        _build_service(
            tmp_path
        )
    )

    issued = service.issue(
        setup_activation_id=(
            _ACTIVATION_ID
        )
    )

    persisted = (
        access_store.storage_path
        .read_text(
            encoding="utf-8"
        )
    )

    assert issued.activation_code not in persisted

    payload = json.loads(
        persisted
    )

    assert set(
        payload["records"][0]
    ) == {
        "access_code_id",
        "setup_activation_id",
        "code_sha256",
        "status",
    }


def test_issuance_repr_redacts_plaintext_code(
    tmp_path,
) -> None:
    _, _, service = _build_service(
        tmp_path
    )

    issued = service.issue(
        setup_activation_id=(
            _ACTIVATION_ID
        )
    )

    rendered = repr(
        issued
    )

    assert issued.activation_code not in rendered
    assert "activation_code=<redacted>" in rendered


def test_authorize_accepts_no_customer_or_activation_identity(
) -> None:
    parameters = inspect.signature(
        CustomerSetupAccessCodeService.authorize
    ).parameters

    assert set(
        parameters
    ) == {
        "self",
        "activation_code",
    }


def test_issue_rejects_unknown_activation(
    tmp_path,
) -> None:
    _, _, service = _build_service(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="Unknown customer setup activation",
    ):
        service.issue(
            setup_activation_id=(
                "setup-activation-unknown"
            )
        )


def test_wrong_code_fails_closed(
    tmp_path,
) -> None:
    _, _, service = _build_service(
        tmp_path
    )

    issued = service.issue(
        setup_activation_id=(
            _ACTIVATION_ID
        )
    )

    wrong = (
        issued.activation_code[:-1]
        + (
            "A"
            if not issued.activation_code.endswith(
                "A"
            )
            else "B"
        )
    )

    with pytest.raises(
        ValueError,
        match="access code is invalid",
    ):
        service.authorize(
            activation_code=wrong
        )


def test_rotation_invalidates_previous_code(
    tmp_path,
) -> None:
    _, access_store, service = (
        _build_service(
            tmp_path
        )
    )

    first = service.issue(
        setup_activation_id=(
            _ACTIVATION_ID
        )
    )

    second = service.issue(
        setup_activation_id=(
            _ACTIVATION_ID
        )
    )

    assert (
        second.activation_code
        != first.activation_code
    )

    first_record = access_store.get(
        access_code_id=(
            first.access_code_id
        )
    )

    assert (
        first_record.status
        is CustomerSetupAccessCodeStatus.REVOKED
    )

    with pytest.raises(
        ValueError,
        match="access code is invalid",
    ):
        service.authorize(
            activation_code=(
                first.activation_code
            )
        )

    assert (
        service.authorize(
            activation_code=(
                second.activation_code
            )
        ).setup_activation_id
        == _ACTIVATION_ID
    )


def test_explicit_revoke_fails_closed(
    tmp_path,
) -> None:
    _, _, service = _build_service(
        tmp_path
    )

    issued = service.issue(
        setup_activation_id=(
            _ACTIVATION_ID
        )
    )

    service.revoke(
        access_code_id=(
            issued.access_code_id
        )
    )

    with pytest.raises(
        ValueError,
        match="access code is invalid",
    ):
        service.authorize(
            activation_code=(
                issued.activation_code
            )
        )


def test_restart_restores_verifier_and_authorizes_code(
    tmp_path,
) -> None:
    (
        activation_store,
        access_store,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = service.issue(
        setup_activation_id=(
            _ACTIVATION_ID
        )
    )

    restored = (
        CustomerSetupAccessCodeStore(
            access_store.storage_path,
            setup_activation_store=(
                activation_store
            ),
        )
    )

    restored_service = (
        CustomerSetupAccessCodeService(
            access_code_store=restored,
            setup_activation_store=(
                activation_store
            ),
        )
    )

    authorized = (
        restored_service.authorize(
            activation_code=(
                issued.activation_code
            )
        )
    )

    assert authorized.customer_id == _CUSTOMER_ID


def test_owner_has_no_payment_http_or_main_dependency(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_access_code_service.py"
    )

    source = source_path.read_text(
        encoding="utf-8"
    ).lower()

    forbidden = (
        "fastapi",
        "paypal",
        "vietqr",
        "payment_id",
        "subscription_id",
        "backend.main",
    )

    for token in forbidden:
        assert token not in source


def test_customer_id_is_not_an_issue_input(
) -> None:
    parameters = inspect.signature(
        CustomerSetupAccessCodeService.issue
    ).parameters

    assert set(
        parameters
    ) == {
        "self",
        "setup_activation_id",
    }