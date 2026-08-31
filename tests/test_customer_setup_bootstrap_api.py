"""
TODOBA Customer Setup Bootstrap Exchange API Tests
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import inspect
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.commercial.customer_setup_bootstrap_api import (
    CustomerSetupBootstrapExchangeRequest,
    CustomerSetupBootstrapExchangeResponse,
    create_customer_setup_bootstrap_router,
)
from backend.commercial.customer_setup_bootstrap_launch_grant_service import (
    CustomerSetupBootstrapLaunchGrantResult,
)


AUTHORIZATION_CODE = (
    "bootstrap-authorization-code"
)

CODE_VERIFIER = (
    "A" * 43
)

SETUP_LAUNCH_CREDENTIAL = (
    "tdbsl."
    + ("b" * 32)
    + "."
    + ("C" * 43)
)

EXPIRES_AT = (
    "2026-08-31T04:00:00+00:00"
)

NOW = datetime(
    2026,
    8,
    31,
    3,
    0,
    0,
    tzinfo=timezone.utc,
)


def _grant(
    *,
    setup_launch_credential: str = (
        SETUP_LAUNCH_CREDENTIAL
    ),
    expires_at: str = EXPIRES_AT,
) -> CustomerSetupBootstrapLaunchGrantResult:
    return CustomerSetupBootstrapLaunchGrantResult(
        authorization_id=(
            "a" * 32
        ),
        customer_id="customer-001",
        consumed_at=(
            "2026-08-31T03:00:00+00:00"
        ),
        launch_issuance_request_id=(
            "bootstrap-launch-"
            + ("d" * 64)
        ),
        launch_id=(
            "b" * 32
        ),
        issued_at=(
            "2026-08-31T03:00:00+00:00"
        ),
        expires_at=expires_at,
        setup_launch_credential=(
            setup_launch_credential
        ),
    )


def _client(
    *,
    grant_setup_launch=None,
    clock=None,
):
    if grant_setup_launch is None:
        grant_setup_launch = (
            lambda **kwargs: _grant()
        )

    if clock is None:
        clock = (
            lambda: NOW
        )

    app = FastAPI()

    app.include_router(
        create_customer_setup_bootstrap_router(
            grant_setup_launch=(
                grant_setup_launch
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
    payload=None,
):
    if payload is None:
        payload = {
            "authorization_code": (
                AUTHORIZATION_CODE
            ),
            "code_verifier": (
                CODE_VERIFIER
            ),
        }

    return client.post(
        "/customer/setup/bootstrap/exchange",
        json=payload,
    )


def test_exchange_returns_only_launch_credential_and_expiry(
) -> None:
    _, client = _client()

    response = _post(
        client
    )

    assert response.status_code == 200

    assert response.json() == {
        "setup_launch_credential": (
            SETUP_LAUNCH_CREDENTIAL
        ),
        "expires_at": EXPIRES_AT,
    }

    assert set(
        response.json()
    ) == {
        "setup_launch_credential",
        "expires_at",
    }


def test_exchange_passes_only_pkce_material_and_trusted_time(
) -> None:
    calls = []

    def grant_setup_launch(
        **kwargs,
    ):
        calls.append(
            kwargs
        )
        return _grant()

    _, client = _client(
        grant_setup_launch=(
            grant_setup_launch
        )
    )

    response = _post(
        client
    )

    assert response.status_code == 200

    assert calls == [
        {
            "authorization_code": (
                AUTHORIZATION_CODE
            ),
            "code_verifier": (
                CODE_VERIFIER
            ),
            "current_time": NOW,
        }
    ]


def test_trusted_clock_is_normalized_to_utc(
) -> None:
    calls = []

    supplied_time = datetime(
        2026,
        8,
        31,
        10,
        0,
        0,
        tzinfo=timezone(
            timedelta(
                hours=7
            )
        ),
    )

    def grant_setup_launch(
        **kwargs,
    ):
        calls.append(
            kwargs
        )
        return _grant()

    _, client = _client(
        grant_setup_launch=(
            grant_setup_launch
        ),
        clock=lambda: supplied_time,
    )

    response = _post(
        client
    )

    assert response.status_code == 200

    assert calls[0][
        "current_time"
    ] == NOW


def test_success_response_is_no_store(
) -> None:
    _, client = _client()

    response = _post(
        client
    )

    assert response.status_code == 200

    assert (
        response.headers[
            "cache-control"
        ]
        == "no-store"
    )


def test_business_rejection_is_generic_403_and_no_store(
) -> None:
    internal_detail = (
        "wrong verifier for customer-001"
    )

    def grant_setup_launch(
        **kwargs,
    ):
        del kwargs
        raise ValueError(
            internal_detail
        )

    _, client = _client(
        grant_setup_launch=(
            grant_setup_launch
        )
    )

    response = _post(
        client
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "Customer setup bootstrap "
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


def test_internal_failure_is_generic_500_and_no_store(
) -> None:
    internal_detail = (
        "durable store invariant failed"
    )

    def grant_setup_launch(
        **kwargs,
    ):
        del kwargs
        raise RuntimeError(
            internal_detail
        )

    _, client = _client(
        grant_setup_launch=(
            grant_setup_launch
        )
    )

    response = _post(
        client
    )

    assert response.status_code == 500

    assert response.json() == {
        "detail": (
            "Customer setup bootstrap failed."
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


def test_invalid_grant_result_fails_closed(
) -> None:
    _, client = _client(
        grant_setup_launch=(
            lambda **kwargs: object()
        )
    )

    response = _post(
        client
    )

    assert response.status_code == 500

    assert response.json() == {
        "detail": (
            "Customer setup bootstrap failed."
        )
    }

    assert (
        response.headers[
            "cache-control"
        ]
        == "no-store"
    )


def test_naive_clock_fails_closed_before_business_call(
) -> None:
    calls = []

    def grant_setup_launch(
        **kwargs,
    ):
        calls.append(
            kwargs
        )
        return _grant()

    _, client = _client(
        grant_setup_launch=(
            grant_setup_launch
        ),
        clock=lambda: datetime(
            2026,
            8,
            31,
            3,
            0,
            0,
        ),
    )

    response = _post(
        client
    )

    assert response.status_code == 500
    assert calls == []

    assert (
        response.headers[
            "cache-control"
        ]
        == "no-store"
    )


def test_non_datetime_clock_fails_closed_before_business_call(
) -> None:
    calls = []

    def grant_setup_launch(
        **kwargs,
    ):
        calls.append(
            kwargs
        )
        return _grant()

    _, client = _client(
        grant_setup_launch=(
            grant_setup_launch
        ),
        clock=lambda: "bad-clock",
    )

    response = _post(
        client
    )

    assert response.status_code == 500
    assert calls == []


def test_clock_exception_fails_closed_without_leak(
) -> None:
    internal_detail = (
        "clock backend detail"
    )

    def bad_clock():
        raise RuntimeError(
            internal_detail
        )

    _, client = _client(
        clock=bad_clock
    )

    response = _post(
        client
    )

    assert response.status_code == 500

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


def test_missing_authorization_code_is_422(
) -> None:
    _, client = _client()

    response = _post(
        client,
        payload={
            "code_verifier": (
                CODE_VERIFIER
            ),
        },
    )

    assert response.status_code == 422


def test_missing_code_verifier_is_422(
) -> None:
    _, client = _client()

    response = _post(
        client,
        payload={
            "authorization_code": (
                AUTHORIZATION_CODE
            ),
        },
    )

    assert response.status_code == 422


def test_extra_customer_identity_is_rejected_by_schema(
) -> None:
    calls = []

    def grant_setup_launch(
        **kwargs,
    ):
        calls.append(
            kwargs
        )
        return _grant()

    _, client = _client(
        grant_setup_launch=(
            grant_setup_launch
        )
    )

    response = _post(
        client,
        payload={
            "authorization_code": (
                AUTHORIZATION_CODE
            ),
            "code_verifier": (
                CODE_VERIFIER
            ),
            "customer_id": (
                "attacker-selected-customer"
            ),
        },
    )

    assert response.status_code == 422
    assert calls == []


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "deployment_id",
        "agent_id",
        "launch_id",
        "authorization_id",
        "grant_request_id",
    ],
)
def test_extra_authority_fields_are_rejected(
    forbidden_field: str,
) -> None:
    _, client = _client()

    payload = {
        "authorization_code": (
            AUTHORIZATION_CODE
        ),
        "code_verifier": (
            CODE_VERIFIER
        ),
        forbidden_field: "forbidden",
    }

    response = _post(
        client,
        payload=payload,
    )

    assert response.status_code == 422


def test_request_repr_redacts_pkce_secrets(
) -> None:
    request = (
        CustomerSetupBootstrapExchangeRequest(
            authorization_code=(
                AUTHORIZATION_CODE
            ),
            code_verifier=(
                CODE_VERIFIER
            ),
        )
    )

    rendered = repr(
        request
    )

    assert (
        AUTHORIZATION_CODE
        not in rendered
    )

    assert (
        CODE_VERIFIER
        not in rendered
    )


def test_response_repr_redacts_launch_credential(
) -> None:
    response = (
        CustomerSetupBootstrapExchangeResponse(
            setup_launch_credential=(
                SETUP_LAUNCH_CREDENTIAL
            ),
            expires_at=EXPIRES_AT,
        )
    )

    rendered = repr(
        response
    )

    assert (
        SETUP_LAUNCH_CREDENTIAL
        not in rendered
    )

    assert response.model_dump() == {
        "setup_launch_credential": (
            SETUP_LAUNCH_CREDENTIAL
        ),
        "expires_at": EXPIRES_AT,
    }


def test_openapi_request_body_has_only_pkce_fields(
) -> None:
    app, _ = _client()

    document = app.openapi()

    operation = (
        document[
            "paths"
        ][
            "/customer/setup/bootstrap/exchange"
        ][
            "post"
        ]
    )

    request_schema = (
        operation[
            "requestBody"
        ][
            "content"
        ][
            "application/json"
        ][
            "schema"
        ]
    )

    reference = request_schema[
        "$ref"
    ]

    schema_name = reference.rsplit(
        "/",
        1,
    )[-1]

    schema = (
        document[
            "components"
        ][
            "schemas"
        ][
            schema_name
        ]
    )

    assert set(
        schema[
            "properties"
        ]
    ) == {
        "authorization_code",
        "code_verifier",
    }

    assert set(
        schema[
            "required"
        ]
    ) == {
        "authorization_code",
        "code_verifier",
    }

    assert (
        schema.get(
            "additionalProperties"
        )
        is False
    )


def test_openapi_has_no_customer_identity_parameter(
) -> None:
    app, _ = _client()

    operation = (
        app.openapi()[
            "paths"
        ][
            "/customer/setup/bootstrap/exchange"
        ][
            "post"
        ]
    )

    parameters = operation.get(
        "parameters",
        []
    )

    assert parameters == []


def test_router_factory_requires_only_boundary_dependencies(
) -> None:
    parameters = (
        inspect.signature(
            create_customer_setup_bootstrap_router
        ).parameters
    )

    assert set(
        parameters
    ) == {
        "grant_setup_launch",
        "clock",
    }

    forbidden = {
        "customer_id",
        "deployment_id",
        "agent_id",
        "authorization_store",
        "launch_store",
        "storage_path",
    }

    assert forbidden.isdisjoint(
        parameters
    )


def test_router_rejects_non_callable_grant_dependency(
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "grant_setup_launch must be callable"
        ),
    ):
        create_customer_setup_bootstrap_router(
            grant_setup_launch=object(),
        )


def test_router_rejects_non_callable_clock(
) -> None:
    with pytest.raises(
        TypeError,
        match="clock must be callable",
    ):
        create_customer_setup_bootstrap_router(
            grant_setup_launch=(
                lambda **kwargs: _grant()
            ),
            clock=object(),
        )


def test_api_owner_has_no_forbidden_authority(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_bootstrap_api.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    forbidden_tokens = (
        "CustomerSetupBootstrapAuthorizationStore",
        "CustomerSetupBootstrapAuthorizationService",
        "CustomerSetupBootstrapLaunchGrantService",
        "CustomerSetupLaunchCredentialStore",
        "CustomerSetupLaunchCredentialService",
        ".issue(",
        ".redeem(",
        "recover_consumed_redemption(",
        "initialize_empty(",
        "open_existing(",
        "backend.main",
        "httpx",
        "os.environ",
        "TODOBA_CLOUD_BASE_URL",
        "package_path",
        "account_fingerprint",
        "MetaTrader5",
    )

    for token in forbidden_tokens:
        assert token not in source
