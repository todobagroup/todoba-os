import json

import pytest

import backend.commercial.customer_vps_connect_grant_http_client as client_module
from backend.commercial.customer_vps_connect_grant_http_client import (
    CustomerVPSConnectGrantHttpClient,
    CustomerVPSConnectGrantTransportResult,
)


BASE_URL = "https://api.todobagroup.com"
ACTIVATION_CODE = "setup-activation-example"
ACCOUNT_FINGERPRINT = "broker|server|123456"
GRANT = "vps-connect-grant.example"
EXPIRES_AT = "2026-09-08T02:00:00+00:00"


class FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        payload: dict,
    ) -> None:
        self.status = status
        self._body = json.dumps(payload).encode(
            "utf-8"
        )

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ) -> None:
        return None


def test_request_contract_is_exact(
    monkeypatch,
) -> None:
    captured = {}

    def fake_urlopen(
        request,
        *,
        timeout,
    ):
        captured["request"] = request
        captured["timeout"] = timeout

        return FakeResponse(
            payload={
                "grant_credential": GRANT,
                "expires_at": EXPIRES_AT,
            }
        )

    monkeypatch.setattr(
        client_module,
        "urlopen",
        fake_urlopen,
    )

    client = CustomerVPSConnectGrantHttpClient(
        cloud_base_url=BASE_URL,
    )

    result = client.issue(
        activation_code=ACTIVATION_CODE,
        account_fingerprint=ACCOUNT_FINGERPRINT,
    )

    request = captured["request"]

    assert request.full_url == (
        BASE_URL
        + "/customer/vps-connect/grant"
    )
    assert request.get_method() == "POST"

    payload = json.loads(
        request.data.decode("utf-8")
    )

    assert payload == {
        "activation_code": ACTIVATION_CODE,
        "account_fingerprint": ACCOUNT_FINGERPRINT,
    }

    assert (
        request.get_header("Content-type")
        == "application/json"
    )
    assert (
        request.get_header("Accept")
        == "application/json"
    )
    assert (
        request.get_header("User-agent")
        == "TODOBA-VPS-Connect/1.0"
    )

    assert captured["timeout"] == 5.0

    assert result == (
        CustomerVPSConnectGrantTransportResult(
            grant_credential=GRANT,
            expires_at=EXPIRES_AT,
        )
    )


def test_trailing_base_url_slash_is_normalized(
    monkeypatch,
) -> None:
    captured = {}

    def fake_urlopen(
        request,
        *,
        timeout,
    ):
        captured["url"] = request.full_url

        return FakeResponse(
            payload={
                "grant_credential": GRANT,
                "expires_at": EXPIRES_AT,
            }
        )

    monkeypatch.setattr(
        client_module,
        "urlopen",
        fake_urlopen,
    )

    client = CustomerVPSConnectGrantHttpClient(
        cloud_base_url=BASE_URL + "/",
    )

    client.issue(
        activation_code=ACTIVATION_CODE,
        account_fingerprint=ACCOUNT_FINGERPRINT,
    )

    assert captured["url"] == (
        BASE_URL
        + "/customer/vps-connect/grant"
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "grant_credential": GRANT,
        },
        {
            "expires_at": EXPIRES_AT,
        },
        {
            "grant_credential": GRANT,
            "expires_at": EXPIRES_AT,
            "customer_id": "forbidden",
        },
        {
            "grant_credential": GRANT,
            "expires_at": EXPIRES_AT,
            "deployment_id": "forbidden",
        },
        {
            "grant_credential": GRANT,
            "expires_at": EXPIRES_AT,
            "agent_id": "forbidden",
        },
        {
            "grant_credential": GRANT,
            "expires_at": EXPIRES_AT,
            "grant_id": "forbidden",
        },
    ],
)
def test_response_shape_must_be_exact(
    monkeypatch,
    payload,
) -> None:
    monkeypatch.setattr(
        client_module,
        "urlopen",
        lambda request, timeout: FakeResponse(
            payload=payload
        ),
    )

    client = CustomerVPSConnectGrantHttpClient(
        cloud_base_url=BASE_URL,
    )

    with pytest.raises(RuntimeError):
        client.issue(
            activation_code=ACTIVATION_CODE,
            account_fingerprint=ACCOUNT_FINGERPRINT,
        )


def test_grant_secret_is_redacted_from_repr() -> None:
    result = CustomerVPSConnectGrantTransportResult(
        grant_credential=GRANT,
        expires_at=EXPIRES_AT,
    )

    assert GRANT not in repr(result)


@pytest.mark.parametrize(
    "cloud_base_url",
    [
        "",
        "   ",
        "ftp://api.todobagroup.com",
        "https://user:pass@api.todobagroup.com",
        "https://api.todobagroup.com/path",
        "https://api.todobagroup.com?x=1",
    ],
)
def test_invalid_base_url_is_rejected(
    cloud_base_url,
) -> None:
    with pytest.raises(
        (TypeError, ValueError),
    ):
        CustomerVPSConnectGrantHttpClient(
            cloud_base_url=cloud_base_url,
        )


@pytest.mark.parametrize(
    "activation_code,account_fingerprint",
    [
        ("", ACCOUNT_FINGERPRINT),
        ("   ", ACCOUNT_FINGERPRINT),
        (ACTIVATION_CODE, ""),
        (ACTIVATION_CODE, "   "),
    ],
)
def test_required_inputs_are_rejected(
    activation_code,
    account_fingerprint,
) -> None:
    client = CustomerVPSConnectGrantHttpClient(
        cloud_base_url=BASE_URL,
    )

    with pytest.raises(
        (TypeError, ValueError),
    ):
        client.issue(
            activation_code=activation_code,
            account_fingerprint=account_fingerprint,
        )


def test_client_has_no_persistence_or_backend_main_dependency(
) -> None:
    from pathlib import Path

    source = Path(
        "backend/commercial/"
        "customer_vps_connect_grant_http_client.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "backend.main" not in source
    assert "open(" not in source
    assert "write_text" not in source
    assert "write_bytes" not in source
    assert "CustomerVPSConnectGrantStore" not in source
