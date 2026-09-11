from __future__ import annotations

import json

import httpx
import pytest

import backend.commercial.customer_paypal_order_http_client as module

from backend.commercial.customer_paypal_order_http_client import (
    CustomerPayPalOrderHttpClient,
    PayPalEnvironment,
)
from backend.commercial.customer_paypal_order_binding_service import (
    PayPalOrderCreationResult,
)


CLIENT_ID = "paypal-client-id-test"
CLIENT_SECRET = "paypal-client-secret-test"
INTENT_ID = "payment-intent-0123456789abcdef"


def _client(
    *,
    environment=PayPalEnvironment.SANDBOX,
):
    return CustomerPayPalOrderHttpClient(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        environment=environment,
        timeout_seconds=10.0,
    )


def _response(
    status_code: int,
    payload,
    *,
    url: str,
):
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request(
            "POST",
            url,
        ),
    )


def _install_success_transport(
    monkeypatch,
    *,
    currency="USD",
    amount_value="19.99",
    paypal_order_id="5O190127TN364715T",
):
    calls = []

    def fake_post(
        url,
        **kwargs,
    ):
        calls.append(
            (
                url,
                kwargs,
            )
        )

        if url.endswith(
            "/v1/oauth2/token"
        ):
            return _response(
                200,
                {
                    "access_token": "access-token-test",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
                url=url,
            )

        assert url.endswith(
            "/v2/checkout/orders"
        )

        return _response(
            201,
            {
                "id": paypal_order_id,
                "status": "CREATED",
                "purchase_units": [
                    {
                        "custom_id": INTENT_ID,
                        "amount": {
                            "currency_code": currency,
                            "value": amount_value,
                        },
                    }
                ],
                "links": [],
            },
            url=url,
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    return calls


def test_sandbox_create_order_uses_oauth_and_authoritative_request(
    monkeypatch,
):
    calls = _install_success_transport(
        monkeypatch,
    )

    result = _client().create_order(
        payment_intent_id=INTENT_ID,
        amount_minor=1999,
        currency="USD",
    )

    assert isinstance(
        result,
        PayPalOrderCreationResult,
    )

    assert result.paypal_order_id == "5O190127TN364715T"
    assert result.paypal_request_id == INTENT_ID
    assert result.custom_id == INTENT_ID
    assert result.amount_minor == 1999
    assert result.currency == "USD"

    assert len(calls) == 2

    token_url, token_kwargs = calls[0]

    assert token_url == (
        "https://api-m.sandbox.paypal.com"
        "/v1/oauth2/token"
    )

    assert token_kwargs["data"] == {
        "grant_type": "client_credentials",
    }

    assert isinstance(
        token_kwargs["auth"],
        httpx.BasicAuth,
    )

    order_url, order_kwargs = calls[1]

    assert order_url == (
        "https://api-m.sandbox.paypal.com"
        "/v2/checkout/orders"
    )

    assert order_kwargs["headers"][
        "Authorization"
    ] == "Bearer access-token-test"

    assert order_kwargs["headers"][
        "PayPal-Request-Id"
    ] == INTENT_ID

    assert order_kwargs["headers"][
        "Prefer"
    ] == "return=representation"

    assert order_kwargs["json"] == {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "custom_id": INTENT_ID,
                "amount": {
                    "currency_code": "USD",
                    "value": "19.99",
                },
            }
        ],
    }


def test_live_environment_uses_only_official_live_origin(
    monkeypatch,
):
    calls = _install_success_transport(
        monkeypatch,
    )

    client = _client(
        environment=PayPalEnvironment.LIVE,
    )

    client.create_order(
        payment_intent_id=INTENT_ID,
        amount_minor=1999,
        currency="USD",
    )

    assert calls[0][0] == (
        "https://api-m.paypal.com"
        "/v1/oauth2/token"
    )

    assert calls[1][0] == (
        "https://api-m.paypal.com"
        "/v2/checkout/orders"
    )


@pytest.mark.parametrize(
    "currency,amount_minor,expected_value",
    (
        ("USD", 1, "0.01"),
        ("USD", 1999, "19.99"),
        ("EUR", 123456, "1234.56"),
        ("JPY", 1999, "1999"),
        ("HUF", 1999, "1999"),
        ("TWD", 1999, "1999"),
    ),
)
def test_amount_minor_is_rendered_without_float(
    monkeypatch,
    currency,
    amount_minor,
    expected_value,
):
    calls = _install_success_transport(
        monkeypatch,
        currency=currency,
        amount_value=expected_value,
    )

    _client().create_order(
        payment_intent_id=INTENT_ID,
        amount_minor=amount_minor,
        currency=currency,
    )

    payload = calls[1][1]["json"]

    assert payload["purchase_units"][0][
        "amount"
    ]["value"] == expected_value


def test_unsupported_paypal_currency_fails_before_network(
    monkeypatch,
):
    called = False

    def forbidden_post(
        *args,
        **kwargs,
    ):
        nonlocal called
        called = True
        raise AssertionError(
            "network must not be called"
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        forbidden_post,
    )

    with pytest.raises(
        ValueError,
        match="currency",
    ):
        _client().create_order(
            payment_intent_id=INTENT_ID,
            amount_minor=1_000_000,
            currency="VND",
        )

    assert called is False


@pytest.mark.parametrize(
    "bad_amount",
    (
        0,
        -1,
        True,
        19.99,
        "1999",
    ),
)
def test_invalid_amount_fails_before_network(
    monkeypatch,
    bad_amount,
):
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: pytest.fail(
            "network must not be called"
        ),
    )

    with pytest.raises(
        (TypeError, ValueError),
    ):
        _client().create_order(
            payment_intent_id=INTENT_ID,
            amount_minor=bad_amount,
            currency="USD",
        )


def test_oauth_failure_stops_before_create_order(
    monkeypatch,
):
    calls = []

    def fake_post(
        url,
        **kwargs,
    ):
        calls.append(url)

        return _response(
            401,
            {
                "error": "invalid_client",
            },
            url=url,
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    with pytest.raises(
        RuntimeError,
        match="OAuth",
    ):
        _client().create_order(
            payment_intent_id=INTENT_ID,
            amount_minor=1999,
            currency="USD",
        )

    assert len(calls) == 1


@pytest.mark.parametrize(
    "payload",
    (
        {},
        {
            "access_token": "",
            "token_type": "Bearer",
        },
        {
            "access_token": "token",
            "token_type": "MAC",
        },
    ),
)
def test_invalid_oauth_response_fails_closed(
    monkeypatch,
    payload,
):
    def fake_post(
        url,
        **kwargs,
    ):
        return _response(
            200,
            payload,
            url=url,
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    with pytest.raises(
        RuntimeError,
        match="OAuth",
    ):
        _client().create_order(
            payment_intent_id=INTENT_ID,
            amount_minor=1999,
            currency="USD",
        )


def test_create_order_http_failure_fails_closed(
    monkeypatch,
):
    count = 0

    def fake_post(
        url,
        **kwargs,
    ):
        nonlocal count
        count += 1

        if count == 1:
            return _response(
                200,
                {
                    "access_token": "access-token-test",
                    "token_type": "Bearer",
                },
                url=url,
            )

        return _response(
            422,
            {
                "name": "UNPROCESSABLE_ENTITY",
            },
            url=url,
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    with pytest.raises(
        RuntimeError,
        match="create order",
    ):
        _client().create_order(
            payment_intent_id=INTENT_ID,
            amount_minor=1999,
            currency="USD",
        )


@pytest.mark.parametrize(
    "mutator",
    (
        lambda payload: {
            **payload,
            "id": "",
        },
        lambda payload: {
            **payload,
            "status": "COMPLETED",
        },
        lambda payload: {
            **payload,
            "purchase_units": [],
        },
        lambda payload: {
            **payload,
            "purchase_units": [
                {
                    "custom_id": "attacker-intent",
                    "amount": {
                        "currency_code": "USD",
                        "value": "19.99",
                    },
                }
            ],
        },
        lambda payload: {
            **payload,
            "purchase_units": [
                {
                    "custom_id": INTENT_ID,
                    "amount": {
                        "currency_code": "EUR",
                        "value": "19.99",
                    },
                }
            ],
        },
        lambda payload: {
            **payload,
            "purchase_units": [
                {
                    "custom_id": INTENT_ID,
                    "amount": {
                        "currency_code": "USD",
                        "value": "99.99",
                    },
                }
            ],
        },
    ),
)
def test_create_order_response_mismatch_fails_closed(
    monkeypatch,
    mutator,
):
    count = 0

    base_payload = {
        "id": "5O190127TN364715T",
        "status": "CREATED",
        "purchase_units": [
            {
                "custom_id": INTENT_ID,
                "amount": {
                    "currency_code": "USD",
                    "value": "19.99",
                },
            }
        ],
    }

    def fake_post(
        url,
        **kwargs,
    ):
        nonlocal count
        count += 1

        if count == 1:
            return _response(
                200,
                {
                    "access_token": "access-token-test",
                    "token_type": "Bearer",
                },
                url=url,
            )

        return _response(
            201,
            mutator(
                base_payload
            ),
            url=url,
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    with pytest.raises(
        RuntimeError,
        match="PayPal order",
    ):
        _client().create_order(
            payment_intent_id=INTENT_ID,
            amount_minor=1999,
            currency="USD",
        )


def test_transport_error_does_not_expose_credentials(
    monkeypatch,
):
    def fail_post(
        *args,
        **kwargs,
    ):
        raise httpx.ConnectError(
            "transport down"
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fail_post,
    )

    with pytest.raises(
        RuntimeError,
    ) as exc_info:
        _client().create_order(
            payment_intent_id=INTENT_ID,
            amount_minor=1999,
            currency="USD",
        )

    message = str(
        exc_info.value
    )

    assert CLIENT_ID not in message
    assert CLIENT_SECRET not in message


def test_client_repr_does_not_expose_secret():
    representation = repr(
        _client()
    )

    assert CLIENT_SECRET not in representation


def test_transport_exposes_no_binding_settlement_or_activation_authority():
    client = _client()

    for name in (
        "bind",
        "receive_evidence",
        "verify_webhook",
        "settle",
        "activate_setup",
        "activate_entitlement",
    ):
        assert not hasattr(
            client,
            name,
        )

@pytest.mark.parametrize(
    "bad_timeout",
    (
        0,
        -1,
        True,
        "10",
        None,
    ),
)
def test_invalid_timeout_is_rejected(
    bad_timeout,
):
    with pytest.raises(
        (TypeError, ValueError),
    ):
        CustomerPayPalOrderHttpClient(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            environment=PayPalEnvironment.SANDBOX,
            timeout_seconds=bad_timeout,
        )


@pytest.mark.parametrize(
    "bad_environment",
    (
        "SANDBOX",
        "LIVE",
        None,
        1,
    ),
)
def test_environment_requires_typed_enum(
    bad_environment,
):
    with pytest.raises(
        TypeError,
        match="PayPalEnvironment",
    ):
        CustomerPayPalOrderHttpClient(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            environment=bad_environment,
            timeout_seconds=10.0,
        )


def test_payment_intent_id_over_custom_id_limit_fails_before_network(
    monkeypatch,
):
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: pytest.fail(
            "network must not be called"
        ),
    )

    oversized = "p" * 256

    with pytest.raises(
        ValueError,
        match="payment_intent_id",
    ):
        _client().create_order(
            payment_intent_id=oversized,
            amount_minor=1999,
            currency="USD",
        )


def test_oauth_non_json_response_fails_closed(
    monkeypatch,
):
    response = httpx.Response(
        200,
        content=b"not-json",
        headers={
            "Content-Type": "text/plain",
        },
        request=httpx.Request(
            "POST",
            (
                "https://api-m.sandbox.paypal.com"
                "/v1/oauth2/token"
            ),
        ),
    )

    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: response,
    )

    with pytest.raises(
        RuntimeError,
        match="OAuth",
    ):
        _client().create_order(
            payment_intent_id=INTENT_ID,
            amount_minor=1999,
            currency="USD",
        )


def test_oauth_json_array_fails_closed(
    monkeypatch,
):
    response = httpx.Response(
        200,
        json=[
            {
                "access_token": "token",
                "token_type": "Bearer",
            }
        ],
        request=httpx.Request(
            "POST",
            (
                "https://api-m.sandbox.paypal.com"
                "/v1/oauth2/token"
            ),
        ),
    )

    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: response,
    )

    with pytest.raises(
        RuntimeError,
        match="OAuth",
    ):
        _client().create_order(
            payment_intent_id=INTENT_ID,
            amount_minor=1999,
            currency="USD",
        )


def test_create_order_non_json_response_fails_closed(
    monkeypatch,
):
    count = 0

    def fake_post(
        url,
        **kwargs,
    ):
        nonlocal count
        count += 1

        if count == 1:
            return _response(
                200,
                {
                    "access_token": "access-token-test",
                    "token_type": "Bearer",
                },
                url=url,
            )

        return httpx.Response(
            201,
            content=b"not-json",
            headers={
                "Content-Type": "text/plain",
            },
            request=httpx.Request(
                "POST",
                url,
            ),
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    with pytest.raises(
        RuntimeError,
        match="PayPal order",
    ):
        _client().create_order(
            payment_intent_id=INTENT_ID,
            amount_minor=1999,
            currency="USD",
        )


def test_create_order_json_array_fails_closed(
    monkeypatch,
):
    count = 0

    def fake_post(
        url,
        **kwargs,
    ):
        nonlocal count
        count += 1

        if count == 1:
            return _response(
                200,
                {
                    "access_token": "access-token-test",
                    "token_type": "Bearer",
                },
                url=url,
            )

        return _response(
            201,
            [
                {
                    "id": "5O190127TN364715T",
                }
            ],
            url=url,
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    with pytest.raises(
        RuntimeError,
        match="PayPal order",
    ):
        _client().create_order(
            payment_intent_id=INTENT_ID,
            amount_minor=1999,
            currency="USD",
        )


def test_access_token_whitespace_is_normalized(
    monkeypatch,
):
    calls = []

    def fake_post(
        url,
        **kwargs,
    ):
        calls.append(
            (
                url,
                kwargs,
            )
        )

        if url.endswith(
            "/v1/oauth2/token"
        ):
            return _response(
                200,
                {
                    "access_token": (
                        "  access-token-test  "
                    ),
                    "token_type": "Bearer",
                },
                url=url,
            )

        return _response(
            201,
            {
                "id": "5O190127TN364715T",
                "status": "CREATED",
                "purchase_units": [
                    {
                        "custom_id": INTENT_ID,
                        "amount": {
                            "currency_code": "USD",
                            "value": "19.99",
                        },
                    }
                ],
            },
            url=url,
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    _client().create_order(
        payment_intent_id=INTENT_ID,
        amount_minor=1999,
        currency="USD",
    )

    assert calls[1][1][
        "headers"
    ]["Authorization"] == (
        "Bearer access-token-test"
    )


def test_response_order_id_is_trimmed(
    monkeypatch,
):
    calls = _install_success_transport(
        monkeypatch,
        paypal_order_id="  5O190127TN364715T  ",
    )

    result = _client().create_order(
        payment_intent_id=INTENT_ID,
        amount_minor=1999,
        currency="USD",
    )

    assert result.paypal_order_id == (
        "5O190127TN364715T"
    )
    assert len(calls) == 2


def test_client_does_not_expose_credentials_as_public_attributes():
    client = _client()

    assert not hasattr(
        client,
        "client_id",
    )
    assert not hasattr(
        client,
        "client_secret",
    )
    assert not hasattr(
        client,
        "access_token",
    )
