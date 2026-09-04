from datetime import datetime, timezone
import inspect
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.commercial.customer_setup_access_code_api import (
    CustomerSetupAccessCodeExchangeRequest,
    CustomerSetupAccessCodeExchangeResponse,
    create_customer_setup_access_code_router,
)
from backend.commercial.customer_setup_access_code_exchange_service import (
    CustomerSetupAccessCodeExchangeResult,
)


_PATH = "/customer/setup/access-code/exchange"

_ACTIVATION_CODE = (
    "tdbsa."
    + ("1" * 32)
    + "."
    + ("A" * 43)
)

_CHALLENGE = "B" * 43

_AUTHORIZATION_CODE = (
    "tdbba."
    + ("2" * 32)
    + "."
    + ("C" * 43)
)

_EXPIRES_AT = datetime(
    2026,
    9,
    4,
    16,
    0,
    tzinfo=timezone.utc,
)


def _client(
    exchange,
) -> TestClient:
    app = FastAPI()

    app.include_router(
        create_customer_setup_access_code_router(
            exchange_setup_access=(
                exchange
            )
        )
    )

    return TestClient(
        app
    )


def test_exchange_forwards_only_activation_code_and_pkce_challenge(
) -> None:
    calls = []

    def exchange(
        **kwargs,
    ):
        calls.append(
            kwargs
        )

        return CustomerSetupAccessCodeExchangeResult(
            authorization_code=(
                _AUTHORIZATION_CODE
            ),
            expires_at=_EXPIRES_AT,
        )

    response = _client(
        exchange
    ).post(
        _PATH,
        json={
            "activation_code": (
                _ACTIVATION_CODE
            ),
            "code_challenge_s256": (
                _CHALLENGE
            ),
        },
    )

    assert response.status_code == 200

    assert calls == [
        {
            "activation_code": (
                _ACTIVATION_CODE
            ),
            "code_challenge_s256": (
                _CHALLENGE
            ),
        }
    ]

    assert response.json() == {
        "authorization_code": (
            _AUTHORIZATION_CODE
        ),
        "expires_at": (
            _EXPIRES_AT.isoformat()
        ),
    }

    assert (
        response.headers[
            "cache-control"
        ]
        == "no-store"
    )


def test_request_model_contains_no_customer_or_setup_identity(
) -> None:
    assert set(
        CustomerSetupAccessCodeExchangeRequest.model_fields
    ) == {
        "activation_code",
        "code_challenge_s256",
    }


def test_response_model_contains_no_customer_or_setup_identity(
) -> None:
    assert set(
        CustomerSetupAccessCodeExchangeResponse.model_fields
    ) == {
        "authorization_code",
        "expires_at",
    }


def test_customer_identity_http_input_is_rejected_before_owner(
) -> None:
    calls = []

    response = _client(
        lambda **kwargs: calls.append(
            kwargs
        )
    ).post(
        _PATH,
        json={
            "activation_code": (
                _ACTIVATION_CODE
            ),
            "code_challenge_s256": (
                _CHALLENGE
            ),
            "customer_id": (
                "customer-attacker"
            ),
        },
    )

    assert response.status_code == 422
    assert calls == []


def test_setup_activation_identity_http_input_is_rejected_before_owner(
) -> None:
    calls = []

    response = _client(
        lambda **kwargs: calls.append(
            kwargs
        )
    ).post(
        _PATH,
        json={
            "activation_code": (
                _ACTIVATION_CODE
            ),
            "code_challenge_s256": (
                _CHALLENGE
            ),
            "setup_activation_id": (
                "setup-activation-attacker"
            ),
        },
    )

    assert response.status_code == 422
    assert calls == []


def test_value_error_is_generic_forbidden_and_no_store(
) -> None:
    def exchange(
        **kwargs,
    ):
        raise ValueError(
            "secret internal rejection reason"
        )

    response = _client(
        exchange
    ).post(
        _PATH,
        json={
            "activation_code": (
                _ACTIVATION_CODE
            ),
            "code_challenge_s256": (
                _CHALLENGE
            ),
        },
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "Customer setup activation "
            "could not be verified."
        )
    }

    assert (
        "secret internal rejection reason"
        not in response.text
    )

    assert (
        response.headers[
            "cache-control"
        ]
        == "no-store"
    )


def test_unexpected_error_is_generic_internal_and_no_store(
) -> None:
    def exchange(
        **kwargs,
    ):
        raise RuntimeError(
            "sensitive server detail"
        )

    response = _client(
        exchange
    ).post(
        _PATH,
        json={
            "activation_code": (
                _ACTIVATION_CODE
            ),
            "code_challenge_s256": (
                _CHALLENGE
            ),
        },
    )

    assert response.status_code == 500

    assert response.json() == {
        "detail": (
            "Customer setup activation "
            "exchange failed."
        )
    }

    assert (
        "sensitive server detail"
        not in response.text
    )

    assert (
        response.headers[
            "cache-control"
        ]
        == "no-store"
    )


def test_invalid_owner_result_fails_closed(
) -> None:
    response = _client(
        lambda **kwargs: object()
    ).post(
        _PATH,
        json={
            "activation_code": (
                _ACTIVATION_CODE
            ),
            "code_challenge_s256": (
                _CHALLENGE
            ),
        },
    )

    assert response.status_code == 500

    assert (
        response.headers[
            "cache-control"
        ]
        == "no-store"
    )


def test_secret_fields_are_redacted_from_model_repr(
) -> None:
    request = CustomerSetupAccessCodeExchangeRequest(
        activation_code=(
            _ACTIVATION_CODE
        ),
        code_challenge_s256=(
            _CHALLENGE
        ),
    )

    response = CustomerSetupAccessCodeExchangeResponse(
        authorization_code=(
            _AUTHORIZATION_CODE
        ),
        expires_at=(
            _EXPIRES_AT.isoformat()
        ),
    )

    assert (
        _ACTIVATION_CODE
        not in repr(request)
    )

    assert (
        _CHALLENGE
        not in repr(request)
    )

    assert (
        _AUTHORIZATION_CODE
        not in repr(response)
    )


def test_router_factory_has_one_narrow_dependency(
) -> None:
    parameters = inspect.signature(
        create_customer_setup_access_code_router
    ).parameters

    assert set(
        parameters
    ) == {
        "exchange_setup_access",
    }


def test_api_owner_has_no_payment_deployment_or_persistence_authority(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_access_code_api.py"
    )

    source = source_path.read_text(
        encoding="utf-8"
    ).lower()

    forbidden = (
        "paypal",
        "vietqr",
        "payment_id",
        "subscription_id",
        "deployment_id",
        "initialize_empty(",
        "open_existing(",
        "customer_setup_access_code_store",
    )

    for token in forbidden:
        assert token not in source