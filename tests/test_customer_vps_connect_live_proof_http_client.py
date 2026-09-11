import json
from urllib.error import HTTPError
from urllib.error import URLError

import pytest

import backend.commercial.customer_vps_connect_live_proof_http_client as client_module

from backend.commercial.customer_vps_connect_live_proof_http_client import (
    CustomerVPSConnectLiveProofHttpClient,
    CustomerVPSConnectLiveProofTransportResult,
)


BASE_URL = "https://api.todobagroup.com"
GRANT = "vps-connect-grant.proof.secret"


class FakeResponse:
    def __init__(
        self,
        *,
        payload,
        status=200,
    ):
        self.status = status
        self._body = json.dumps(
            payload
        ).encode(
            "utf-8"
        )

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    def read(self):
        return self._body


@pytest.mark.parametrize(
    "status",
    [
        "runtime_ready",
        "vps_pending",
        "vps_online",
    ],
)
def test_verify_posts_grant_only_and_returns_status(
    monkeypatch,
    status,
):
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
                "status": status,
            },
        )

    monkeypatch.setattr(
        client_module,
        "urlopen",
        fake_urlopen,
    )

    client = CustomerVPSConnectLiveProofHttpClient(
        cloud_base_url=BASE_URL,
    )

    result = client.verify(
        grant_credential=GRANT,
    )

    request = captured["request"]

    assert request.full_url == (
        BASE_URL
        + "/customer/vps-connect/live-proof"
    )

    assert request.get_method() == "POST"

    assert json.loads(
        request.data.decode("utf-8")
    ) == {
        "grant_credential": GRANT,
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
        CustomerVPSConnectLiveProofTransportResult(
            status=status,
        )
    )


def test_trailing_base_url_slash_is_normalized(
    monkeypatch,
):
    captured = {}

    def fake_urlopen(
        request,
        *,
        timeout,
    ):
        captured["url"] = request.full_url

        return FakeResponse(
            payload={
                "status": "vps_pending",
            },
        )

    monkeypatch.setattr(
        client_module,
        "urlopen",
        fake_urlopen,
    )

    client = CustomerVPSConnectLiveProofHttpClient(
        cloud_base_url=BASE_URL + "/",
    )

    client.verify(
        grant_credential=GRANT,
    )

    assert captured["url"] == (
        BASE_URL
        + "/customer/vps-connect/live-proof"
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "status": "vps_online",
            "agent_id": "forbidden",
        },
        {
            "status": "vps_online",
            "account_fingerprint": "forbidden",
        },
        {
            "status": "vps_online",
            "customer_id": "forbidden",
        },
        {
            "status": "vps_online",
            "deployment_id": "forbidden",
        },
    ],
)
def test_response_shape_must_be_exact(
    monkeypatch,
    payload,
):
    monkeypatch.setattr(
        client_module,
        "urlopen",
        lambda request, timeout: FakeResponse(
            payload=payload,
        ),
    )

    client = CustomerVPSConnectLiveProofHttpClient(
        cloud_base_url=BASE_URL,
    )

    with pytest.raises(
        RuntimeError,
    ):
        client.verify(
            grant_credential=GRANT,
        )


@pytest.mark.parametrize(
    "status",
    [
        "",
        "online",
        "grant_ready",
        "failed",
        None,
        123,
    ],
)
def test_status_domain_is_exact(
    monkeypatch,
    status,
):
    monkeypatch.setattr(
        client_module,
        "urlopen",
        lambda request, timeout: FakeResponse(
            payload={
                "status": status,
            },
        ),
    )

    client = CustomerVPSConnectLiveProofHttpClient(
        cloud_base_url=BASE_URL,
    )

    with pytest.raises(
        RuntimeError,
    ):
        client.verify(
            grant_credential=GRANT,
        )


def test_non_200_response_fails_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        client_module,
        "urlopen",
        lambda request, timeout: FakeResponse(
            payload={
                "status": "vps_pending",
            },
            status=500,
        ),
    )

    client = CustomerVPSConnectLiveProofHttpClient(
        cloud_base_url=BASE_URL,
    )

    with pytest.raises(
        RuntimeError,
        match="live proof request failed",
    ):
        client.verify(
            grant_credential=GRANT,
        )


@pytest.mark.parametrize(
    "transport_error",
    [
        URLError("offline"),
        TimeoutError("timeout"),
        OSError("network"),
    ],
)
def test_transport_failure_is_generic_and_redacts_grant(
    monkeypatch,
    transport_error,
):
    def fake_urlopen(
        request,
        *,
        timeout,
    ):
        raise transport_error

    monkeypatch.setattr(
        client_module,
        "urlopen",
        fake_urlopen,
    )

    client = CustomerVPSConnectLiveProofHttpClient(
        cloud_base_url=BASE_URL,
    )

    with pytest.raises(
        RuntimeError,
    ) as exc_info:
        client.verify(
            grant_credential=GRANT,
        )

    assert GRANT not in str(
        exc_info.value
    )


def test_http_error_is_generic_and_redacts_grant(
    monkeypatch,
):
    def fake_urlopen(
        request,
        *,
        timeout,
    ):
        raise HTTPError(
            request.full_url,
            403,
            "forbidden",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(
        client_module,
        "urlopen",
        fake_urlopen,
    )

    client = CustomerVPSConnectLiveProofHttpClient(
        cloud_base_url=BASE_URL,
    )

    with pytest.raises(
        RuntimeError,
    ) as exc_info:
        client.verify(
            grant_credential=GRANT,
        )

    assert GRANT not in str(
        exc_info.value
    )


def test_result_surface_contains_only_status():
    result = (
        CustomerVPSConnectLiveProofTransportResult(
            status="vps_online",
        )
    )

    assert tuple(
        result.__dataclass_fields__
    ) == ("status",)


@pytest.mark.parametrize(
    "cloud_base_url",
    [
        "",
        "   ",
        "ftp://api.todobagroup.com",
        "https://user:pass@api.todobagroup.com",
        "https://api.todobagroup.com/path",
        "https://api.todobagroup.com?query=yes",
        "https://api.todobagroup.com#fragment",
    ],
)
def test_invalid_cloud_base_url_is_rejected(
    cloud_base_url,
):
    with pytest.raises(
        (TypeError, ValueError),
    ):
        CustomerVPSConnectLiveProofHttpClient(
            cloud_base_url=cloud_base_url,
        )


@pytest.mark.parametrize(
    "timeout_seconds",
    [
        0,
        -1,
        "5",
        None,
    ],
)
def test_invalid_timeout_is_rejected(
    timeout_seconds,
):
    with pytest.raises(
        (TypeError, ValueError),
    ):
        CustomerVPSConnectLiveProofHttpClient(
            cloud_base_url=BASE_URL,
            timeout_seconds=timeout_seconds,
        )


@pytest.mark.parametrize(
    "grant_credential",
    [
        "",
        "   ",
        None,
        123,
    ],
)
def test_invalid_grant_is_rejected_before_transport(
    monkeypatch,
    grant_credential,
):
    calls = []

    monkeypatch.setattr(
        client_module,
        "urlopen",
        lambda *args, **kwargs: calls.append(
            (args, kwargs)
        ),
    )

    client = CustomerVPSConnectLiveProofHttpClient(
        cloud_base_url=BASE_URL,
    )

    with pytest.raises(
        (TypeError, ValueError),
    ):
        client.verify(
            grant_credential=grant_credential,
        )

    assert calls == []


def test_owner_has_no_extra_authority():
    source = (
        __import__("pathlib")
        .Path(
            "backend/commercial/"
            "customer_vps_connect_live_proof_http_client.py"
        )
        .read_text(
            encoding="utf-8-sig",
        )
    )

    for forbidden in (
        "CustomerVPSConnectGrantStore",
        "BrokerStateStore",
        "MetaTrader5",
        "common.ini",
        "WebRequestUrl",
        "subprocess",
        "pywinauto",
        "uiautomation",
        "write_text",
        "write_bytes",
        "initialize_empty",
    ):
        assert forbidden not in source