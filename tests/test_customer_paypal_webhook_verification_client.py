from __future__ import annotations

import httpx
import pytest

import backend.commercial.customer_paypal_webhook_verification_client as module

from backend.commercial.customer_paypal_order_http_client import (
    PayPalEnvironment,
)
from backend.commercial.customer_paypal_webhook_verification_client import (
    CustomerPayPalWebhookVerificationClient,
    PayPalWebhookVerificationResult,
)


CLIENT_ID = "paypal-client-id-test"
CLIENT_SECRET = "paypal-client-secret-test"
WEBHOOK_ID = "5K7935027W328883P"

TRANSMISSION_ID = "69cd13f0-d67a-11e5-baa3-778b53f4ae55"
TRANSMISSION_TIME = "2026-09-11T08:00:00Z"
CERT_URL = (
    "https://api-m.sandbox.paypal.com/"
    "v1/notifications/certs/CERT-360caa42"
)
AUTH_ALGO = "SHA256withRSA"
TRANSMISSION_SIG = "signature-test"

WEBHOOK_EVENT = {
    "id": "WH-123456789",
    "event_type": "PAYMENT.CAPTURE.COMPLETED",
    "resource_type": "capture",
    "resource": {
        "id": "8MC585209K746392H",
        "status": "COMPLETED",
    },
}


def _client(
    *,
    environment=PayPalEnvironment.SANDBOX,
):
    return CustomerPayPalWebhookVerificationClient(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        webhook_id=WEBHOOK_ID,
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


def _headers():
    return {
        "PAYPAL-TRANSMISSION-ID": TRANSMISSION_ID,
        "PAYPAL-TRANSMISSION-TIME": TRANSMISSION_TIME,
        "PAYPAL-CERT-URL": CERT_URL,
        "PAYPAL-AUTH-ALGO": AUTH_ALGO,
        "PAYPAL-TRANSMISSION-SIG": TRANSMISSION_SIG,
    }


def _install_success_transport(
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
                    "access_token": "access-token-test",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
                url=url,
            )

        assert url.endswith(
            "/v1/notifications/verify-webhook-signature"
        )

        return _response(
            200,
            {
                "verification_status": "SUCCESS",
            },
            url=url,
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    return calls


def test_valid_webhook_is_verified_by_paypal(
    monkeypatch,
):
    calls = _install_success_transport(
        monkeypatch,
    )

    result = _client().verify(
        headers=_headers(),
        webhook_event=WEBHOOK_EVENT,
    )

    assert isinstance(
        result,
        PayPalWebhookVerificationResult,
    )

    assert result.webhook_event_id == "WH-123456789"
    assert result.event_type == (
        "PAYMENT.CAPTURE.COMPLETED"
    )
    assert result.verification_status == "SUCCESS"

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

    verify_url, verify_kwargs = calls[1]

    assert verify_url == (
        "https://api-m.sandbox.paypal.com"
        "/v1/notifications/verify-webhook-signature"
    )

    assert verify_kwargs["headers"][
        "Authorization"
    ] == "Bearer access-token-test"

    assert verify_kwargs["json"] == {
        "transmission_id": TRANSMISSION_ID,
        "transmission_time": TRANSMISSION_TIME,
        "cert_url": CERT_URL,
        "auth_algo": AUTH_ALGO,
        "transmission_sig": TRANSMISSION_SIG,
        "webhook_id": WEBHOOK_ID,
        "webhook_event": WEBHOOK_EVENT,
    }


def test_live_environment_uses_live_paypal_origin(
    monkeypatch,
):
    calls = _install_success_transport(
        monkeypatch,
    )

    client = _client(
        environment=PayPalEnvironment.LIVE,
    )

    client.verify(
        headers=_headers(),
        webhook_event=WEBHOOK_EVENT,
    )

    assert calls[0][0] == (
        "https://api-m.paypal.com"
        "/v1/oauth2/token"
    )

    assert calls[1][0] == (
        "https://api-m.paypal.com"
        "/v1/notifications/verify-webhook-signature"
    )


@pytest.mark.parametrize(
    "missing_header",
    (
        "PAYPAL-TRANSMISSION-ID",
        "PAYPAL-TRANSMISSION-TIME",
        "PAYPAL-CERT-URL",
        "PAYPAL-AUTH-ALGO",
        "PAYPAL-TRANSMISSION-SIG",
    ),
)
def test_missing_required_header_fails_before_network(
    monkeypatch,
    missing_header,
):
    headers = _headers()
    del headers[
        missing_header
    ]

    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: pytest.fail(
            "network must not be called"
        ),
    )

    with pytest.raises(
        ValueError,
        match="header",
    ):
        _client().verify(
            headers=headers,
            webhook_event=WEBHOOK_EVENT,
        )


def test_webhook_event_must_be_object(
    monkeypatch,
):
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: pytest.fail(
            "network must not be called"
        ),
    )

    with pytest.raises(
        TypeError,
        match="webhook_event",
    ):
        _client().verify(
            headers=_headers(),
            webhook_event=[
                WEBHOOK_EVENT,
            ],
        )


@pytest.mark.parametrize(
    "bad_event",
    (
        {},
        {
            "id": "",
            "event_type": (
                "PAYMENT.CAPTURE.COMPLETED"
            ),
        },
        {
            "id": "WH-123",
            "event_type": "",
        },
    ),
)
def test_webhook_event_identity_is_required_before_network(
    monkeypatch,
    bad_event,
):
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: pytest.fail(
            "network must not be called"
        ),
    )

    with pytest.raises(
        ValueError,
        match="webhook",
    ):
        _client().verify(
            headers=_headers(),
            webhook_event=bad_event,
        )


def test_oauth_failure_stops_before_verification(
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
        _client().verify(
            headers=_headers(),
            webhook_event=WEBHOOK_EVENT,
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
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda url, **kwargs: _response(
            200,
            payload,
            url=url,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="OAuth",
    ):
        _client().verify(
            headers=_headers(),
            webhook_event=WEBHOOK_EVENT,
        )


@pytest.mark.parametrize(
    "verification_payload",
    (
        {},
        {
            "verification_status": "FAILURE",
        },
        {
            "verification_status": "",
        },
        {
            "verification_status": True,
        },
    ),
)
def test_non_success_verification_fails_closed(
    monkeypatch,
    verification_payload,
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
                    "access_token": "token",
                    "token_type": "Bearer",
                },
                url=url,
            )

        return _response(
            200,
            verification_payload,
            url=url,
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    with pytest.raises(
        ValueError,
        match="signature",
    ):
        _client().verify(
            headers=_headers(),
            webhook_event=WEBHOOK_EVENT,
        )


def test_verification_http_failure_fails_closed(
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
                    "access_token": "token",
                    "token_type": "Bearer",
                },
                url=url,
            )

        return _response(
            500,
            {
                "name": "INTERNAL_SERVER_ERROR",
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
        match="verification",
    ):
        _client().verify(
            headers=_headers(),
            webhook_event=WEBHOOK_EVENT,
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
        _client().verify(
            headers=_headers(),
            webhook_event=WEBHOOK_EVENT,
        )

    message = str(
        exc_info.value
    )

    assert CLIENT_ID not in message
    assert CLIENT_SECRET not in message


def test_client_repr_does_not_expose_secret_or_webhook_id():
    representation = repr(
        _client()
    )

    assert CLIENT_SECRET not in representation
    assert WEBHOOK_ID not in representation


def test_transport_exposes_no_business_or_settlement_authority():
    client = _client()

    for name in (
        "bind",
        "receive_evidence",
        "verify_capture",
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
        CustomerPayPalWebhookVerificationClient(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            webhook_id=WEBHOOK_ID,
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
        CustomerPayPalWebhookVerificationClient(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            webhook_id=WEBHOOK_ID,
            environment=bad_environment,
            timeout_seconds=10.0,
        )


@pytest.mark.parametrize(
    "name,value",
    (
        ("client_id", ""),
        ("client_secret", ""),
        ("webhook_id", ""),
    ),
)
def test_required_constructor_strings_reject_empty(
    name,
    value,
):
    kwargs = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "webhook_id": WEBHOOK_ID,
        "environment": PayPalEnvironment.SANDBOX,
        "timeout_seconds": 10.0,
    }

    kwargs[name] = value

    with pytest.raises(
        ValueError,
    ):
        CustomerPayPalWebhookVerificationClient(
            **kwargs
        )


def test_paypal_headers_are_case_insensitive_and_trimmed(
    monkeypatch,
):
    calls = _install_success_transport(
        monkeypatch,
    )

    headers = {
        "paypal-transmission-id": (
            f"  {TRANSMISSION_ID}  "
        ),
        "paypal-transmission-time": (
            f"  {TRANSMISSION_TIME}  "
        ),
        "paypal-cert-url": (
            f"  {CERT_URL}  "
        ),
        "paypal-auth-algo": (
            f"  {AUTH_ALGO}  "
        ),
        "paypal-transmission-sig": (
            f"  {TRANSMISSION_SIG}  "
        ),
    }

    result = _client().verify(
        headers=headers,
        webhook_event=WEBHOOK_EVENT,
    )

    assert result.verification_status == "SUCCESS"

    payload = calls[1][1]["json"]

    assert payload["transmission_id"] == TRANSMISSION_ID
    assert payload["transmission_time"] == TRANSMISSION_TIME
    assert payload["cert_url"] == CERT_URL
    assert payload["auth_algo"] == AUTH_ALGO
    assert payload["transmission_sig"] == TRANSMISSION_SIG


@pytest.mark.parametrize(
    "bad_headers",
    (
        [],
        "headers",
        None,
    ),
)
def test_headers_must_be_dict(
    monkeypatch,
    bad_headers,
):
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: pytest.fail(
            "network must not be called"
        ),
    )

    with pytest.raises(
        TypeError,
        match="headers",
    ):
        _client().verify(
            headers=bad_headers,
            webhook_event=WEBHOOK_EVENT,
        )


def test_non_string_header_value_fails_before_network(
    monkeypatch,
):
    headers = _headers()
    headers[
        "PAYPAL-TRANSMISSION-ID"
    ] = 123

    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: pytest.fail(
            "network must not be called"
        ),
    )

    with pytest.raises(
        TypeError,
        match="header",
    ):
        _client().verify(
            headers=headers,
            webhook_event=WEBHOOK_EVENT,
        )


def test_empty_required_header_fails_before_network(
    monkeypatch,
):
    headers = _headers()
    headers[
        "PAYPAL-TRANSMISSION-SIG"
    ] = "   "

    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: pytest.fail(
            "network must not be called"
        ),
    )

    with pytest.raises(
        ValueError,
        match="header",
    ):
        _client().verify(
            headers=headers,
            webhook_event=WEBHOOK_EVENT,
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
        _client().verify(
            headers=_headers(),
            webhook_event=WEBHOOK_EVENT,
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
            url=url,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="OAuth",
    ):
        _client().verify(
            headers=_headers(),
            webhook_event=WEBHOOK_EVENT,
        )


def test_verification_non_json_response_fails_closed(
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
                    "access_token": "token",
                    "token_type": "Bearer",
                },
                url=url,
            )

        return httpx.Response(
            200,
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
        match="verification",
    ):
        _client().verify(
            headers=_headers(),
            webhook_event=WEBHOOK_EVENT,
        )


def test_verification_json_array_fails_closed(
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
                    "access_token": "token",
                    "token_type": "Bearer",
                },
                url=url,
            )

        return _response(
            200,
            [
                {
                    "verification_status": "SUCCESS",
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
        match="verification",
    ):
        _client().verify(
            headers=_headers(),
            webhook_event=WEBHOOK_EVENT,
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
                    "access_token": "  token-test  ",
                    "token_type": "Bearer",
                },
                url=url,
            )

        return _response(
            200,
            {
                "verification_status": "SUCCESS",
            },
            url=url,
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    _client().verify(
        headers=_headers(),
        webhook_event=WEBHOOK_EVENT,
    )

    assert (
        calls[1][1]["headers"]["Authorization"]
        == "Bearer token-test"
    )


def test_result_contains_only_authenticity_identity():
    result = PayPalWebhookVerificationResult(
        webhook_event_id="WH-123",
        event_type="PAYMENT.CAPTURE.COMPLETED",
        verification_status="SUCCESS",
    )

    assert set(
        result.__dict__
    ) == {
        "webhook_event_id",
        "event_type",
        "verification_status",
    }


@pytest.mark.parametrize(
    "bad_status",
    (
        "",
        "FAILURE",
        "PENDING",
    ),
)
def test_result_type_rejects_non_success_status(
    bad_status,
):
    with pytest.raises(
        ValueError,
    ):
        PayPalWebhookVerificationResult(
            webhook_event_id="WH-123",
            event_type="PAYMENT.CAPTURE.COMPLETED",
            verification_status=bad_status,
        )


def test_client_does_not_expose_credentials_or_webhook_id_publicly():
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
    assert not hasattr(
        client,
        "webhook_id",
    )


def test_webhook_event_is_not_mutated(
    monkeypatch,
):
    _install_success_transport(
        monkeypatch,
    )

    event = {
        "id": WEBHOOK_EVENT["id"],
        "event_type": WEBHOOK_EVENT["event_type"],
        "resource_type": WEBHOOK_EVENT["resource_type"],
        "resource": {
            "id": WEBHOOK_EVENT["resource"]["id"],
            "status": WEBHOOK_EVENT["resource"]["status"],
        },
    }

    before = {
        "id": event["id"],
        "event_type": event["event_type"],
        "resource_type": event["resource_type"],
        "resource": dict(
            event["resource"]
        ),
    }

    _client().verify(
        headers=_headers(),
        webhook_event=event,
    )

    assert event == before
