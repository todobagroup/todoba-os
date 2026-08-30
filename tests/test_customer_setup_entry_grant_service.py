"""
Owner tests for Customer Setup Entry Grant Service.
"""

from datetime import datetime
from datetime import timezone
import ast
from pathlib import Path
from unittest.mock import Mock

import pytest

from backend.commercial.customer_registration_service import (
    CustomerRegistrationRecord,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationResult,
    CustomerSetupActivationStatus,
)
from backend.commercial.customer_setup_entry_grant_service import (
    CustomerSetupEntryGrantResult,
    CustomerSetupEntryGrantService,
)
from backend.commercial.customer_setup_handoff_service import (
    CustomerSetupHandoffIssuanceResult,
)


GRANT_REQUEST_ID = "grant-request-001"
REGISTRATION_REQUEST_ID = "registration-request-001"
CUSTOMER_ID = "customer-001"
SETUP_ACTIVATION_ID = "setup-activation-001"
HANDOFF_ID = (
    "0123456789abcdef0123456789abcdef"
)
ISSUED_AT = "2030-01-01T00:00:00Z"
EXPIRES_AT = "2030-01-01T00:15:00Z"
HANDOFF_CREDENTIAL = "tdbsh1.test-secret"
CURRENT_TIME = datetime(
    2030,
    1,
    1,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)


def _registration_record(
    *,
    registration_request_id: str = (
        REGISTRATION_REQUEST_ID
    ),
    customer_id: str = CUSTOMER_ID,
) -> CustomerRegistrationRecord:
    return CustomerRegistrationRecord(
        registration_request_id=(
            registration_request_id
        ),
        customer_id=customer_id,
    )


def _activation_result(
    *,
    activation_request_id: str = (
        GRANT_REQUEST_ID
    ),
    setup_activation_id: str = (
        SETUP_ACTIVATION_ID
    ),
    customer_id: str = CUSTOMER_ID,
) -> CustomerSetupActivationResult:
    return CustomerSetupActivationResult(
        activation_request_id=(
            activation_request_id
        ),
        setup_activation_id=(
            setup_activation_id
        ),
        customer_id=customer_id,
        status=(
            CustomerSetupActivationStatus.ACTIVE
        ),
    )


def _handoff_result(
    *,
    issuance_request_id: str = (
        GRANT_REQUEST_ID
    ),
    handoff_id: str = HANDOFF_ID,
    setup_activation_id: str = (
        SETUP_ACTIVATION_ID
    ),
    handoff_credential: str = (
        HANDOFF_CREDENTIAL
    ),
) -> CustomerSetupHandoffIssuanceResult:
    return CustomerSetupHandoffIssuanceResult(
        issuance_request_id=(
            issuance_request_id
        ),
        handoff_id=handoff_id,
        setup_activation_id=(
            setup_activation_id
        ),
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
        handoff_credential=(
            handoff_credential
        ),
    )


def _build_service(
    *,
    registration_record=...,
    activation_result=...,
    handoff_result=...,
):
    registration_store = Mock()
    setup_activation_service = Mock()
    handoff_service = Mock()

    if registration_record is ...:
        registration_record = (
            _registration_record()
        )

    if activation_result is ...:
        activation_result = (
            _activation_result()
        )

    if handoff_result is ...:
        handoff_result = (
            _handoff_result()
        )

    registration_store.get_by_customer_id.return_value = (
        registration_record
    )
    setup_activation_service.activate.return_value = (
        activation_result
    )
    handoff_service.issue.return_value = (
        handoff_result
    )

    service = CustomerSetupEntryGrantService(
        registration_store=(
            registration_store
        ),
        setup_activation_service=(
            setup_activation_service
        ),
        handoff_service=handoff_service,
    )

    return (
        service,
        registration_store,
        setup_activation_service,
        handoff_service,
    )


def test_result_redacts_handoff_credential_from_repr() -> None:
    result = CustomerSetupEntryGrantResult(
        grant_request_id=GRANT_REQUEST_ID,
        registration_request_id=(
            REGISTRATION_REQUEST_ID
        ),
        customer_id=CUSTOMER_ID,
        setup_activation_id=SETUP_ACTIVATION_ID,
        handoff_id=HANDOFF_ID,
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
        handoff_credential=HANDOFF_CREDENTIAL,
    )

    rendered = repr(
        result
    )

    assert HANDOFF_CREDENTIAL not in rendered
    assert "handoff_credential=<redacted>" in rendered


@pytest.mark.parametrize(
    (
        "dependency_name",
        "registration_store",
        "activation_service",
        "handoff_service",
        "expected",
    ),
    (
        (
            "registration_store",
            object(),
            Mock(),
            Mock(),
            (
                "registration_store must expose callable "
                "get_by_customer_id"
            ),
        ),
        (
            "setup_activation_service",
            Mock(),
            object(),
            Mock(),
            (
                "setup_activation_service must expose "
                "callable activate"
            ),
        ),
        (
            "handoff_service",
            Mock(),
            Mock(),
            object(),
            (
                "handoff_service must expose callable "
                "issue"
            ),
        ),
    ),
)
def test_service_requires_owner_methods(
    dependency_name,
    registration_store,
    activation_service,
    handoff_service,
    expected,
) -> None:
    del dependency_name

    with pytest.raises(
        TypeError,
        match=expected,
    ):
        CustomerSetupEntryGrantService(
            registration_store=(
                registration_store
            ),
            setup_activation_service=(
                activation_service
            ),
            handoff_service=handoff_service,
        )


def test_grant_requires_authoritative_registration() -> None:
    (
        service,
        _,
        activation_service,
        handoff_service,
    ) = _build_service(
        registration_record=None
    )

    with pytest.raises(
        ValueError,
        match=(
            "Customer is not authoritatively "
            "registered"
        ),
    ):
        service.grant(
            grant_request_id=GRANT_REQUEST_ID,
            customer_id=CUSTOMER_ID,
            current_time=CURRENT_TIME,
        )

    activation_service.activate.assert_not_called()
    handoff_service.issue.assert_not_called()


def test_invalid_registration_result_fails_closed() -> None:
    (
        service,
        _,
        activation_service,
        handoff_service,
    ) = _build_service(
        registration_record=object()
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "registration store returned invalid record"
        ),
    ):
        service.grant(
            grant_request_id=GRANT_REQUEST_ID,
            customer_id=CUSTOMER_ID,
            current_time=CURRENT_TIME,
        )

    activation_service.activate.assert_not_called()
    handoff_service.issue.assert_not_called()


def test_registration_customer_mismatch_fails_closed() -> None:
    (
        service,
        _,
        activation_service,
        handoff_service,
    ) = _build_service(
        registration_record=(
            _registration_record(
                customer_id="customer-other"
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "registration identity mismatch"
        ),
    ):
        service.grant(
            grant_request_id=GRANT_REQUEST_ID,
            customer_id=CUSTOMER_ID,
            current_time=CURRENT_TIME,
        )

    activation_service.activate.assert_not_called()
    handoff_service.issue.assert_not_called()


def test_grant_composes_authoritative_owners() -> None:
    (
        service,
        registration_store,
        activation_service,
        handoff_service,
    ) = _build_service()

    result = service.grant(
        grant_request_id=GRANT_REQUEST_ID,
        customer_id=CUSTOMER_ID,
        current_time=CURRENT_TIME,
    )

    registration_store.get_by_customer_id.assert_called_once_with(
        customer_id=CUSTOMER_ID
    )
    activation_service.activate.assert_called_once_with(
        activation_request_id=GRANT_REQUEST_ID,
        customer_id=CUSTOMER_ID,
    )
    handoff_service.issue.assert_called_once_with(
        issuance_request_id=GRANT_REQUEST_ID,
        setup_activation_id=SETUP_ACTIVATION_ID,
        current_time=CURRENT_TIME,
    )

    assert result.grant_request_id == GRANT_REQUEST_ID
    assert (
        result.registration_request_id
        == REGISTRATION_REQUEST_ID
    )
    assert result.customer_id == CUSTOMER_ID
    assert (
        result.setup_activation_id
        == SETUP_ACTIVATION_ID
    )
    assert result.handoff_id == HANDOFF_ID
    assert result.issued_at == ISSUED_AT
    assert result.expires_at == EXPIRES_AT
    assert (
        result.handoff_credential
        == HANDOFF_CREDENTIAL
    )


def test_grant_normalizes_customer_controlled_identity() -> None:
    (
        service,
        registration_store,
        activation_service,
        handoff_service,
    ) = _build_service()

    result = service.grant(
        grant_request_id=(
            f" {GRANT_REQUEST_ID} "
        ),
        customer_id=f" {CUSTOMER_ID} ",
        current_time=CURRENT_TIME,
    )

    assert result.grant_request_id == GRANT_REQUEST_ID
    assert result.customer_id == CUSTOMER_ID

    registration_store.get_by_customer_id.assert_called_once_with(
        customer_id=CUSTOMER_ID
    )
    activation_service.activate.assert_called_once_with(
        activation_request_id=GRANT_REQUEST_ID,
        customer_id=CUSTOMER_ID,
    )
    handoff_service.issue.assert_called_once_with(
        issuance_request_id=GRANT_REQUEST_ID,
        setup_activation_id=SETUP_ACTIVATION_ID,
        current_time=CURRENT_TIME,
    )


@pytest.mark.parametrize(
    (
        "grant_request_id",
        "customer_id",
        "current_time",
        "exception_type",
        "match",
    ),
    (
        (
            "",
            CUSTOMER_ID,
            CURRENT_TIME,
            ValueError,
            "grant_request_id is required",
        ),
        (
            GRANT_REQUEST_ID,
            "",
            CURRENT_TIME,
            ValueError,
            "customer_id is required",
        ),
        (
            GRANT_REQUEST_ID,
            CUSTOMER_ID,
            "2030-01-01T00:00:00Z",
            TypeError,
            "current_time must be datetime",
        ),
    ),
)
def test_grant_rejects_invalid_inputs(
    grant_request_id,
    customer_id,
    current_time,
    exception_type,
    match,
) -> None:
    (
        service,
        _,
        activation_service,
        handoff_service,
    ) = _build_service()

    with pytest.raises(
        exception_type,
        match=match,
    ):
        service.grant(
            grant_request_id=grant_request_id,
            customer_id=customer_id,
            current_time=current_time,
        )

    activation_service.activate.assert_not_called()
    handoff_service.issue.assert_not_called()


def test_invalid_activation_result_fails_closed() -> None:
    (
        service,
        _,
        _,
        handoff_service,
    ) = _build_service(
        activation_result=object()
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "activation service returned invalid result"
        ),
    ):
        service.grant(
            grant_request_id=GRANT_REQUEST_ID,
            customer_id=CUSTOMER_ID,
            current_time=CURRENT_TIME,
        )

    handoff_service.issue.assert_not_called()


def test_activation_request_mismatch_fails_closed() -> None:
    (
        service,
        _,
        _,
        handoff_service,
    ) = _build_service(
        activation_result=(
            _activation_result(
                activation_request_id=(
                    "grant-request-other"
                )
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "activation request identity did not converge"
        ),
    ):
        service.grant(
            grant_request_id=GRANT_REQUEST_ID,
            customer_id=CUSTOMER_ID,
            current_time=CURRENT_TIME,
        )

    handoff_service.issue.assert_not_called()


def test_activation_customer_mismatch_fails_closed() -> None:
    (
        service,
        _,
        _,
        handoff_service,
    ) = _build_service(
        activation_result=(
            _activation_result(
                customer_id="customer-other"
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "activation customer identity mismatch"
        ),
    ):
        service.grant(
            grant_request_id=GRANT_REQUEST_ID,
            customer_id=CUSTOMER_ID,
            current_time=CURRENT_TIME,
        )

    handoff_service.issue.assert_not_called()


def test_invalid_handoff_result_fails_closed() -> None:
    (
        service,
        _,
        _,
        _,
    ) = _build_service(
        handoff_result=object()
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "handoff service returned invalid result"
        ),
    ):
        service.grant(
            grant_request_id=GRANT_REQUEST_ID,
            customer_id=CUSTOMER_ID,
            current_time=CURRENT_TIME,
        )


def test_handoff_request_mismatch_fails_closed() -> None:
    (
        service,
        _,
        _,
        _,
    ) = _build_service(
        handoff_result=(
            _handoff_result(
                issuance_request_id=(
                    "grant-request-other"
                )
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "handoff request identity did not converge"
        ),
    ):
        service.grant(
            grant_request_id=GRANT_REQUEST_ID,
            customer_id=CUSTOMER_ID,
            current_time=CURRENT_TIME,
        )


def test_handoff_activation_mismatch_fails_closed() -> None:
    (
        service,
        _,
        _,
        _,
    ) = _build_service(
        handoff_result=(
            _handoff_result(
                setup_activation_id=(
                    "setup-activation-other"
                )
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "handoff activation identity mismatch"
        ),
    ):
        service.grant(
            grant_request_id=GRANT_REQUEST_ID,
            customer_id=CUSTOMER_ID,
            current_time=CURRENT_TIME,
        )


def test_retry_reuses_downstream_identity_and_returns_rotated_secret(
) -> None:
    (
        service,
        _,
        activation_service,
        handoff_service,
    ) = _build_service()

    activation_service.activate.side_effect = (
        _activation_result(),
        _activation_result(),
    )
    handoff_service.issue.side_effect = (
        _handoff_result(
            handoff_credential="tdbsh1.secret-one"
        ),
        _handoff_result(
            handoff_credential="tdbsh1.secret-two"
        ),
    )

    first = service.grant(
        grant_request_id=GRANT_REQUEST_ID,
        customer_id=CUSTOMER_ID,
        current_time=CURRENT_TIME,
    )
    second = service.grant(
        grant_request_id=GRANT_REQUEST_ID,
        customer_id=CUSTOMER_ID,
        current_time=CURRENT_TIME,
    )

    assert (
        first.setup_activation_id
        == second.setup_activation_id
        == SETUP_ACTIVATION_ID
    )
    assert (
        first.handoff_id
        == second.handoff_id
        == HANDOFF_ID
    )
    assert (
        first.handoff_credential
        != second.handoff_credential
    )

    assert activation_service.activate.call_count == 2
    assert handoff_service.issue.call_count == 2


def test_owner_has_no_http_or_runtime_composition_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_entry_grant_service.py"
    )
    source = path.read_text(
        encoding="utf-8-sig"
    )
    tree = ast.parse(
        source
    )

    imported_modules: set[str] = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            imported_modules.update(
                alias.name
                for alias in node.names
            )

        if isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module is not None:
                imported_modules.add(
                    node.module
                )

    assert "fastapi" not in imported_modules
    assert "backend.main" not in imported_modules

    assert not any(
        module.startswith(
            "backend.trading"
        )
        for module in imported_modules
    )


def test_owner_has_no_duplicate_persistence_surface() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_entry_grant_service.py"
    )
    source = path.read_text(
        encoding="utf-8-sig"
    )

    forbidden = (
        "initialize_empty(",
        "storage_path",
        "os.replace(",
        "json.dump",
        "json.dumps",
    )

    for token in forbidden:
        assert token not in source
