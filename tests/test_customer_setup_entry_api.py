"""
Owner tests for TODOBA Customer Setup Entry Exchange API.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import inspect
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.commercial.customer_setup_entry_api import (
    CustomerSetupEntryResponse,
    create_customer_setup_entry_router,
)
from backend.commercial.customer_setup_entry_grant_service import (
    CustomerSetupEntryGrantResult,
)
from backend.commercial.customer_setup_launch_credential_service import (
    CustomerSetupLaunchAuthorization,
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

LAUNCH_ID = (
    "0123456789abcdef0123456789abcdef"
)

LAUNCH_CREDENTIAL = (
    "tdbsl."
    + LAUNCH_ID
    + "."
    + ("A" * 43)
)

HANDOFF_CREDENTIAL = (
    "tdbsh."
    + ("1" * 32)
    + "."
    + ("B" * 43)
)

CUSTOMER_ID = "customer-001"

ISSUED_AT = (
    "2026-08-30T10:00:00.000000Z"
)

EXPIRES_AT = (
    "2026-08-30T10:15:00.000000Z"
)


def _authorization(
    *,
    launch_id: str = LAUNCH_ID,
    customer_id: str = CUSTOMER_ID,
) -> CustomerSetupLaunchAuthorization:
    return CustomerSetupLaunchAuthorization(
        launch_id=launch_id,
        customer_id=customer_id,
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
    )


def _grant(
    *,
    grant_request_id: str = LAUNCH_ID,
    customer_id: str = CUSTOMER_ID,
    handoff_credential: str = HANDOFF_CREDENTIAL,
) -> CustomerSetupEntryGrantResult:
    return CustomerSetupEntryGrantResult(
        grant_request_id=(
            grant_request_id
        ),
        registration_request_id=(
            "registration-request-001"
        ),
        customer_id=customer_id,
        setup_activation_id=(
            "setup-activation-001"
        ),
        handoff_id="handoff-001",
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
        handoff_credential=(
            handoff_credential
        ),
    )


def _client(
    *,
    authorize_setup_launch=None,
    grant_setup_entry=None,
    clock=None,
):
    if authorize_setup_launch is None:
        authorize_setup_launch = (
            lambda **kwargs: _authorization()
        )

    if grant_setup_entry is None:
        grant_setup_entry = (
            lambda **kwargs: _grant()
        )

    if clock is None:
        clock = lambda: NOW

    app = FastAPI()

    app.include_router(
        create_customer_setup_entry_router(
            authorize_setup_launch=(
                authorize_setup_launch
            ),
            grant_setup_entry=(
                grant_setup_entry
            ),
            clock=clock,
        )
    )

    return (
        app,
        TestClient(
            app,
            raise_server_exceptions=False,
        ),
    )


def _post(
    client: TestClient,
    *,
    authorization=(
        f"Bearer {LAUNCH_CREDENTIAL}"
    ),
):
    headers = {}

    if authorization is not None:
        headers[
            "Authorization"
        ] = authorization

    return client.post(
        "/customer/setup/entry",
        headers=headers,
    )


def test_success_returns_only_handoff_and_expiry() -> None:
    _, client = _client()

    response = _post(
        client
    )

    assert response.status_code == 200
    assert response.json() == {
        "handoff_credential": (
            HANDOFF_CREDENTIAL
        ),
        "expires_at": EXPIRES_AT,
    }

    assert (
        "customer_id"
        not in response.text
    )
    assert (
        "grant_request_id"
        not in response.text
    )
    assert (
        "setup_activation_id"
        not in response.text
    )
    assert (
        "handoff_id"
        not in response.text
    )
    assert (
        LAUNCH_CREDENTIAL
        not in response.text
    )


def test_success_response_is_not_cacheable() -> None:
    _, client = _client()

    response = _post(
        client
    )

    assert (
        response.headers[
            "cache-control"
        ]
        == "no-store"
    )
    assert (
        response.headers[
            "pragma"
        ]
        == "no-cache"
    )


def test_launch_authorizer_receives_exact_bearer_and_server_time() -> None:
    calls = []

    def authorize_setup_launch(
        *,
        launch_credential,
        current_time,
    ):
        calls.append(
            (
                launch_credential,
                current_time,
            )
        )
        return _authorization()

    _, client = _client(
        authorize_setup_launch=(
            authorize_setup_launch
        )
    )

    response = _post(
        client
    )

    assert response.status_code == 200
    assert calls == [
        (
            LAUNCH_CREDENTIAL,
            NOW,
        )
    ]


def test_entry_grant_uses_only_authoritative_launch_identity() -> None:
    calls = []

    authoritative_customer = (
        "authoritative-customer"
    )

    def authorize_setup_launch(
        **kwargs,
    ):
        del kwargs

        return _authorization(
            customer_id=(
                authoritative_customer
            )
        )

    def grant_setup_entry(
        *,
        grant_request_id,
        customer_id,
        current_time,
    ):
        calls.append(
            {
                "grant_request_id": (
                    grant_request_id
                ),
                "customer_id": (
                    customer_id
                ),
                "current_time": (
                    current_time
                ),
            }
        )

        return _grant(
            customer_id=(
                authoritative_customer
            )
        )

    _, client = _client(
        authorize_setup_launch=(
            authorize_setup_launch
        ),
        grant_setup_entry=(
            grant_setup_entry
        ),
    )

    response = _post(
        client
    )

    assert response.status_code == 200

    assert calls == [
        {
            "grant_request_id": (
                LAUNCH_ID
            ),
            "customer_id": (
                authoritative_customer
            ),
            "current_time": NOW,
        }
    ]


@pytest.mark.parametrize(
    "authorization",
    (
        None,
        "",
        "Basic abc",
        "Bearer",
        "Bearer ",
        "Bearer  token",
        "Bearer token ",
        " Bearer token",
    ),
)
def test_invalid_authorization_transport_returns_401(
    authorization,
) -> None:
    _, client = _client()

    response = _post(
        client,
        authorization=authorization,
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": (
            "Customer setup launch "
            "authentication failed."
        )
    }

    assert (
        response.headers[
            "www-authenticate"
        ]
        == "Bearer"
    )
    assert (
        response.headers[
            "cache-control"
        ]
        == "no-store"
    )


def test_launch_authorization_failure_converges_on_401() -> None:
    internal_detail = (
        "expired credential abc-secret"
    )

    def authorize_setup_launch(
        **kwargs,
    ):
        del kwargs
        raise ValueError(
            internal_detail
        )

    _, client = _client(
        authorize_setup_launch=(
            authorize_setup_launch
        )
    )

    response = _post(
        client
    )

    assert response.status_code == 401
    assert (
        internal_detail
        not in response.text
    )
    assert (
        LAUNCH_CREDENTIAL
        not in response.text
    )


def test_invalid_launch_authorizer_result_fails_closed() -> None:
    _, client = _client(
        authorize_setup_launch=(
            lambda **kwargs: object()
        )
    )

    response = _post(
        client
    )

    assert response.status_code == 500


def test_entry_grant_value_error_is_safe_403() -> None:
    internal_detail = (
        "customer internal setup detail"
    )

    def grant_setup_entry(
        **kwargs,
    ):
        del kwargs
        raise ValueError(
            internal_detail
        )

    _, client = _client(
        grant_setup_entry=(
            grant_setup_entry
        )
    )

    response = _post(
        client
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Customer setup entry "
            "is not available."
        )
    }
    assert (
        internal_detail
        not in response.text
    )
    assert (
        response.headers[
            "cache-control"
        ]
        == "no-store"
    )


def test_invalid_entry_grant_result_fails_closed() -> None:
    _, client = _client(
        grant_setup_entry=(
            lambda **kwargs: object()
        )
    )

    response = _post(
        client
    )

    assert response.status_code == 500


def test_grant_request_identity_must_converge() -> None:
    _, client = _client(
        grant_setup_entry=(
            lambda **kwargs: _grant(
                grant_request_id=(
                    "wrong-request-id"
                )
            )
        )
    )

    response = _post(
        client
    )

    assert response.status_code == 500


def test_grant_customer_identity_must_converge() -> None:
    _, client = _client(
        grant_setup_entry=(
            lambda **kwargs: _grant(
                customer_id=(
                    "wrong-customer"
                )
            )
        )
    )

    response = _post(
        client
    )

    assert response.status_code == 500


def test_same_trusted_clock_value_is_used_for_auth_and_grant() -> None:
    calls = []

    supplied_time = datetime(
        2026,
        8,
        30,
        17,
        0,
        0,
        tzinfo=timezone(
            timedelta(
                hours=7
            )
        ),
    )

    expected_utc = supplied_time.astimezone(
        timezone.utc
    )

    def authorize_setup_launch(
        *,
        launch_credential,
        current_time,
    ):
        del launch_credential
        calls.append(
            (
                "authorize",
                current_time,
            )
        )
        return _authorization()

    def grant_setup_entry(
        *,
        grant_request_id,
        customer_id,
        current_time,
    ):
        del grant_request_id
        del customer_id
        calls.append(
            (
                "grant",
                current_time,
            )
        )
        return _grant()

    _, client = _client(
        authorize_setup_launch=(
            authorize_setup_launch
        ),
        grant_setup_entry=(
            grant_setup_entry
        ),
        clock=lambda: supplied_time,
    )

    response = _post(
        client
    )

    assert response.status_code == 200
    assert calls == [
        (
            "authorize",
            expected_utc,
        ),
        (
            "grant",
            expected_utc,
        ),
    ]


def test_naive_clock_fails_closed_before_business_calls() -> None:
    calls = []

    def authorize_setup_launch(
        **kwargs,
    ):
        calls.append(
            kwargs
        )
        return _authorization()

    _, client = _client(
        authorize_setup_launch=(
            authorize_setup_launch
        ),
        clock=lambda: datetime(
            2026,
            8,
            30,
            10,
            0,
            0,
        ),
    )

    response = _post(
        client
    )

    assert response.status_code == 500
    assert calls == []


def test_non_datetime_clock_fails_closed() -> None:
    _, client = _client(
        clock=lambda: "bad-clock",
    )

    response = _post(
        client
    )

    assert response.status_code == 500


def test_response_repr_redacts_handoff_credential() -> None:
    response = CustomerSetupEntryResponse(
        handoff_credential=(
            HANDOFF_CREDENTIAL
        ),
        expires_at=EXPIRES_AT,
    )

    rendered = repr(
        response
    )

    assert (
        HANDOFF_CREDENTIAL
        not in rendered
    )
    assert (
        response.model_dump()
        == {
            "handoff_credential": (
                HANDOFF_CREDENTIAL
            ),
            "expires_at": EXPIRES_AT,
        }
    )


def test_openapi_has_no_customer_request_body() -> None:
    app, _ = _client()

    operation = (
        app.openapi()[
            "paths"
        ][
            "/customer/setup/entry"
        ][
            "post"
        ]
    )

    assert (
        "requestBody"
        not in operation
    )

    parameters = operation.get(
        "parameters",
        []
    )

    assert len(
        parameters
    ) == 1
    assert (
        parameters[0][
            "name"
        ]
        == "Authorization"
    )
    assert (
        parameters[0][
            "in"
        ]
        == "header"
    )


def test_router_factory_requires_only_boundary_dependencies() -> None:
    parameters = (
        inspect.signature(
            create_customer_setup_entry_router
        ).parameters
    )

    assert set(
        parameters
    ) == {
        "authorize_setup_launch",
        "grant_setup_entry",
        "clock",
    }

    forbidden = {
        "customer_id",
        "deployment_id",
        "agent_id",
        "registration_request_id",
        "grant_request_id",
        "storage_path",
    }

    assert forbidden.isdisjoint(
        parameters
    )


def test_router_rejects_non_callable_dependencies() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "authorize_setup_launch must be callable"
        ),
    ):
        create_customer_setup_entry_router(
            authorize_setup_launch=object(),
            grant_setup_entry=lambda **kwargs: (
                _grant()
            ),
        )

    with pytest.raises(
        TypeError,
        match=(
            "grant_setup_entry must be callable"
        ),
    ):
        create_customer_setup_entry_router(
            authorize_setup_launch=(
                lambda **kwargs: _authorization()
            ),
            grant_setup_entry=object(),
        )

    with pytest.raises(
        TypeError,
        match="clock must be callable",
    ):
        create_customer_setup_entry_router(
            authorize_setup_launch=(
                lambda **kwargs: _authorization()
            ),
            grant_setup_entry=(
                lambda **kwargs: _grant()
            ),
            clock=object(),
        )


def test_api_owner_has_no_forbidden_authority() -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_entry_api.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    forbidden_tokens = (
        "CustomerSetupLaunchCredentialStore",
        "CustomerSetupLaunchCredentialService",
        ".issue(",
        "initialize_empty(",
        "open_existing(",
        "CustomerRegistrationService",
        "CustomerSetupActivationService",
        "CustomerSetupHandoffService",
        "CustomerDeployment",
        "MetaTrader5",
        "httpx",
        "backend.main",
        "os.environ",
        "TODOBA_CLOUD_BASE_URL",
        "package_path",
        "account_fingerprint",
    )

    for token in forbidden_tokens:
        assert token not in source