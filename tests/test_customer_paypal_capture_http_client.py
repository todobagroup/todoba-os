from __future__ import annotations

import httpx
import pytest

import backend.commercial.customer_paypal_capture_http_client as module

from backend.commercial.customer_paypal_order_http_client import (
    PayPalEnvironment,
)
from backend.commercial.customer_paypal_capture_http_client import (
    CustomerPayPalCaptureHttpClient,
    PayPalCaptureDetails,
)


CLIENT_ID = "paypal-client-id-test"
CLIENT_SECRET = "paypal-client-secret-test"

CAPTURE_ID = "8MC585209K746392H"
ORDER_ID = "5O190127TN364715T"
CUSTOM_ID = "payment-intent-0123456789abcdef"


def _client(
    *,
    environment=PayPalEnvironment.SANDBOX,
):
    return CustomerPayPalCaptureHttpClient(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        environment=environment,
        timeout_seconds=10.0,
    )


def _response(
    status_code: int,
    payload,
    *,
    method: str,
    url: str,
):
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request(
            method,
            url,
        ),
    )


def _capture_payload(
    *,
    capture_id=CAPTURE_ID,
    order_id=ORDER_ID,
    custom_id=CUSTOM_ID,
    currency="USD",
    value="19.99",
    status="COMPLETED",
):
    return {
        "id": capture_id,
        "status": status,
        "amount": {
            "currency_code": currency,
            "value": value,
        },
        "custom_id": custom_id,
        "supplementary_data": {
            "related_ids": {
                "order_id": order_id,
            }
        },
    }


def _install_success_transport(
    monkeypatch,
    *,
    payload=None,
):
    calls = []

    def fake_post(
        url,
        **kwargs,
    ):
        calls.append(
            (
                "POST",
                url,
                kwargs,
            )
        )

        return _response(
            200,
            {
                "access_token": "access-token-test",
                "token_type": "Bearer",
            },
            method="POST",
            url=url,
        )

    def fake_get(
        url,
        **kwargs,
    ):
        calls.append(
            (
                "GET",
                url,
                kwargs,
            )
        )

        return _response(
            200,
            (
                _capture_payload()
                if payload is None
                else payload
            ),
            method="GET",
            url=url,
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    monkeypatch.setattr(
        module.httpx,
        "get",
        fake_get,
    )

    return calls


def test_fetch_completed_capture_from_paypal(
    monkeypatch,
):
    calls = _install_success_transport(
        monkeypatch,
    )

    result = _client().get_capture(
        capture_id=CAPTURE_ID,
    )

    assert isinstance(
        result,
        PayPalCaptureDetails,
    )

    assert result.capture_id == CAPTURE_ID
    assert result.order_id == ORDER_ID
    assert result.custom_id == CUSTOM_ID
    assert result.amount_minor == 1999
    assert result.currency == "USD"
    assert result.status == "COMPLETED"

    assert len(calls) == 2

    assert calls[0][0] == "POST"

    assert calls[0][1] == (
        "https://api-m.sandbox.paypal.com"
        "/v1/oauth2/token"
    )

    assert isinstance(
        calls[0][2]["auth"],
        httpx.BasicAuth,
    )

    assert calls[1][0] == "GET"

    assert calls[1][1] == (
        "https://api-m.sandbox.paypal.com"
        f"/v2/payments/captures/{CAPTURE_ID}"
    )

    assert calls[1][2]["headers"][
        "Authorization"
    ] == "Bearer access-token-test"


def test_live_environment_uses_live_paypal_origin(
    monkeypatch,
):
    calls = _install_success_transport(
        monkeypatch,
    )

    _client(
        environment=PayPalEnvironment.LIVE,
    ).get_capture(
        capture_id=CAPTURE_ID,
    )

    assert calls[0][1] == (
        "https://api-m.paypal.com"
        "/v1/oauth2/token"
    )

    assert calls[1][1] == (
        "https://api-m.paypal.com"
        f"/v2/payments/captures/{CAPTURE_ID}"
    )


@pytest.mark.parametrize(
    "currency,value,expected_minor",
    (
        ("USD", "0.01", 1),
        ("USD", "19.99", 1999),
        ("EUR", "1234.56", 123456),
        ("JPY", "1999", 1999),
        ("HUF", "1999", 1999),
        ("TWD", "1999", 1999),
    ),
)
def test_amount_is_parsed_without_float(
    monkeypatch,
    currency,
    value,
    expected_minor,
):
    _install_success_transport(
        monkeypatch,
        payload=_capture_payload(
            currency=currency,
            value=value,
        ),
    )

    result = _client().get_capture(
        capture_id=CAPTURE_ID,
    )

    assert result.amount_minor == expected_minor
    assert result.currency == currency


@pytest.mark.parametrize(
    "bad_value",
    (
        "",
        "19",
        "19.9",
        "19.999",
        "abc",
        "-1.00",
        "0.00",
    ),
)
def test_invalid_two_decimal_amount_fails_closed(
    monkeypatch,
    bad_value,
):
    _install_success_transport(
        monkeypatch,
        payload=_capture_payload(
            currency="USD",
            value=bad_value,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="capture",
    ):
        _client().get_capture(
            capture_id=CAPTURE_ID,
        )


@pytest.mark.parametrize(
    "bad_value",
    (
        "",
        "19.00",
        "19.9",
        "-1",
        "0",
        "abc",
    ),
)
def test_invalid_zero_decimal_amount_fails_closed(
    monkeypatch,
    bad_value,
):
    _install_success_transport(
        monkeypatch,
        payload=_capture_payload(
            currency="JPY",
            value=bad_value,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="capture",
    ):
        _client().get_capture(
            capture_id=CAPTURE_ID,
        )


def test_non_completed_capture_fails_closed(
    monkeypatch,
):
    _install_success_transport(
        monkeypatch,
        payload=_capture_payload(
            status="PENDING",
        ),
    )

    with pytest.raises(
        ValueError,
        match="COMPLETED",
    ):
        _client().get_capture(
            capture_id=CAPTURE_ID,
        )


@pytest.mark.parametrize(
    "mutator",
    (
        lambda p: {
            **p,
            "id": "",
        },
        lambda p: {
            **p,
            "custom_id": "",
        },
        lambda p: {
            **p,
            "amount": {},
        },
        lambda p: {
            **p,
            "supplementary_data": {},
        },
        lambda p: {
            **p,
            "supplementary_data": {
                "related_ids": {},
            },
        },
    ),
)
def test_missing_capture_business_identity_fails_closed(
    monkeypatch,
    mutator,
):
    payload = mutator(
        _capture_payload()
    )

    _install_success_transport(
        monkeypatch,
        payload=payload,
    )

    with pytest.raises(
        RuntimeError,
        match="capture",
    ):
        _client().get_capture(
            capture_id=CAPTURE_ID,
        )


def test_requested_capture_id_must_match_provider_response(
    monkeypatch,
):
    _install_success_transport(
        monkeypatch,
        payload=_capture_payload(
            capture_id="DIFFERENTCAPTURE123",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="capture",
    ):
        _client().get_capture(
            capture_id=CAPTURE_ID,
        )


def test_oauth_failure_stops_before_capture_fetch(
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
            method="POST",
            url=url,
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    monkeypatch.setattr(
        module.httpx,
        "get",
        lambda *args, **kwargs: pytest.fail(
            "capture fetch must not run"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="OAuth",
    ):
        _client().get_capture(
            capture_id=CAPTURE_ID,
        )

    assert len(calls) == 1


def test_capture_http_failure_fails_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda url, **kwargs: _response(
            200,
            {
                "access_token": "token",
                "token_type": "Bearer",
            },
            method="POST",
            url=url,
        ),
    )

    monkeypatch.setattr(
        module.httpx,
        "get",
        lambda url, **kwargs: _response(
            404,
            {
                "name": "RESOURCE_NOT_FOUND",
            },
            method="GET",
            url=url,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="capture",
    ):
        _client().get_capture(
            capture_id=CAPTURE_ID,
        )


def test_transport_error_does_not_expose_credentials(
    monkeypatch,
):
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: (
            (_ for _ in ())
            .throw(
                httpx.ConnectError(
                    "transport down"
                )
            )
        ),
    )

    with pytest.raises(
        RuntimeError,
    ) as exc_info:
        _client().get_capture(
            capture_id=CAPTURE_ID,
        )

    message = str(
        exc_info.value
    )

    assert CLIENT_ID not in message
    assert CLIENT_SECRET not in message


def test_result_contains_only_capture_business_truth():
    result = PayPalCaptureDetails(
        capture_id=CAPTURE_ID,
        order_id=ORDER_ID,
        custom_id=CUSTOM_ID,
        amount_minor=1999,
        currency="USD",
        status="COMPLETED",
    )

    assert set(
        result.__dict__
    ) == {
        "capture_id",
        "order_id",
        "custom_id",
        "amount_minor",
        "currency",
        "status",
    }


def test_transport_exposes_no_settlement_or_activation_authority():
    client = _client()

    for name in (
        "bind",
        "receive_evidence",
        "build_assertion",
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
        CustomerPayPalCaptureHttpClient(
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
        CustomerPayPalCaptureHttpClient(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            environment=bad_environment,
            timeout_seconds=10.0,
        )


@pytest.mark.parametrize(
    "name,value",
    (
        ("client_id", ""),
        ("client_secret", ""),
    ),
)
def test_required_constructor_strings_reject_empty(
    name,
    value,
):
    kwargs = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "environment": PayPalEnvironment.SANDBOX,
        "timeout_seconds": 10.0,
    }

    kwargs[name] = value

    with pytest.raises(
        ValueError,
    ):
        CustomerPayPalCaptureHttpClient(
            **kwargs
        )


def test_capture_id_is_trimmed_before_request(
    monkeypatch,
):
    calls = _install_success_transport(
        monkeypatch,
    )

    result = _client().get_capture(
        capture_id=f"  {CAPTURE_ID}  ",
    )

    assert result.capture_id == CAPTURE_ID
    assert calls[1][1].endswith(
        f"/v2/payments/captures/{CAPTURE_ID}"
    )


@pytest.mark.parametrize(
    "bad_capture_id",
    (
        "",
        "   ",
        None,
        123,
    ),
)
def test_invalid_capture_id_fails_before_network(
    monkeypatch,
    bad_capture_id,
):
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: pytest.fail(
            "network must not be called"
        ),
    )

    monkeypatch.setattr(
        module.httpx,
        "get",
        lambda *args, **kwargs: pytest.fail(
            "network must not be called"
        ),
    )

    with pytest.raises(
        (TypeError, ValueError),
    ):
        _client().get_capture(
            capture_id=bad_capture_id,
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

    monkeypatch.setattr(
        module.httpx,
        "get",
        lambda *args, **kwargs: pytest.fail(
            "capture fetch must not run"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="OAuth",
    ):
        _client().get_capture(
            capture_id=CAPTURE_ID,
        )


def test_oauth_json_array_fails_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda url, **kwargs: _response(
            200,
            [
                {
                    "access_token": "token",
                    "token_type": "Bearer",
                }
            ],
            method="POST",
            url=url,
        ),
    )

    monkeypatch.setattr(
        module.httpx,
        "get",
        lambda *args, **kwargs: pytest.fail(
            "capture fetch must not run"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="OAuth",
    ):
        _client().get_capture(
            capture_id=CAPTURE_ID,
        )


def test_capture_non_json_response_fails_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda url, **kwargs: _response(
            200,
            {
                "access_token": "token",
                "token_type": "Bearer",
            },
            method="POST",
            url=url,
        ),
    )

    monkeypatch.setattr(
        module.httpx,
        "get",
        lambda url, **kwargs: httpx.Response(
            200,
            content=b"not-json",
            headers={
                "Content-Type": "text/plain",
            },
            request=httpx.Request(
                "GET",
                url,
            ),
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="capture",
    ):
        _client().get_capture(
            capture_id=CAPTURE_ID,
        )


def test_capture_json_array_fails_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda url, **kwargs: _response(
            200,
            {
                "access_token": "token",
                "token_type": "Bearer",
            },
            method="POST",
            url=url,
        ),
    )

    monkeypatch.setattr(
        module.httpx,
        "get",
        lambda url, **kwargs: _response(
            200,
            [
                _capture_payload()
            ],
            method="GET",
            url=url,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="capture",
    ):
        _client().get_capture(
            capture_id=CAPTURE_ID,
        )


def test_access_token_whitespace_is_trimmed(
    monkeypatch,
):
    calls = []

    def fake_post(
        url,
        **kwargs,
    ):
        calls.append(
            (
                "POST",
                url,
                kwargs,
            )
        )

        return _response(
            200,
            {
                "access_token": "  token-test  ",
                "token_type": "Bearer",
            },
            method="POST",
            url=url,
        )

    def fake_get(
        url,
        **kwargs,
    ):
        calls.append(
            (
                "GET",
                url,
                kwargs,
            )
        )

        return _response(
            200,
            _capture_payload(),
            method="GET",
            url=url,
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    monkeypatch.setattr(
        module.httpx,
        "get",
        fake_get,
    )

    _client().get_capture(
        capture_id=CAPTURE_ID,
    )

    assert (
        calls[1][2]["headers"]["Authorization"]
        == "Bearer token-test"
    )


def test_client_repr_does_not_expose_secret():
    representation = repr(
        _client()
    )

    assert CLIENT_SECRET not in representation


def test_client_does_not_expose_credentials_publicly():
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


@pytest.mark.parametrize(
    "bad_status",
    (
        "",
        "PENDING",
        "DECLINED",
    ),
)
def test_capture_details_rejects_non_completed_status(
    bad_status,
):
    with pytest.raises(
        ValueError,
        match="COMPLETED",
    ):
        PayPalCaptureDetails(
            capture_id=CAPTURE_ID,
            order_id=ORDER_ID,
            custom_id=CUSTOM_ID,
            amount_minor=1999,
            currency="USD",
            status=bad_status,
        )


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
def test_capture_details_rejects_invalid_amount(
    bad_amount,
):
    with pytest.raises(
        (TypeError, ValueError),
    ):
        PayPalCaptureDetails(
            capture_id=CAPTURE_ID,
            order_id=ORDER_ID,
            custom_id=CUSTOM_ID,
            amount_minor=bad_amount,
            currency="USD",
            status="COMPLETED",
        )


def test_capture_details_rejects_unsupported_currency():
    with pytest.raises(
        ValueError,
        match="currency",
    ):
        PayPalCaptureDetails(
            capture_id=CAPTURE_ID,
            order_id=ORDER_ID,
            custom_id=CUSTOM_ID,
            amount_minor=1_000_000,
            currency="VND",
            status="COMPLETED",
        )
