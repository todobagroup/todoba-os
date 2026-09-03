"""
Owner tests for Customer Setup HTTP Client.
"""

import ast
from pathlib import Path

import httpx
import pytest

import backend.commercial.customer_setup_http_client as module
from backend.commercial.customer_setup_http_client import (
    CustomerSetupHttpClient,
    CustomerSetupProvisioningTransportResult,
)


BASE_URL = "https://api.todobagroup.com"
HANDOFF_CREDENTIAL = "tdbsh1.super-secret"
ACCOUNT_FINGERPRINT = "Broker-Server:12345678"
ARTIFACT_SHA256 = "a" * 64
ARTIFACT_SIZE_BYTES = 1234
ARTIFACT_CONTENT = b"TODOBA EX5 package"


def _response(
    status_code: int,
    *,
    json=None,
    content: bytes | None = None,
    headers: dict[str, str] | None = None,
    method: str = "POST",
    url: str = BASE_URL,
) -> httpx.Response:
    request = httpx.Request(
        method,
        url,
    )

    if content is not None:
        return httpx.Response(
            status_code,
            content=content,
            headers=headers,
            request=request,
        )

    return httpx.Response(
        status_code,
        json=json,
        headers=headers,
        request=request,
    )


def _client() -> CustomerSetupHttpClient:
    return CustomerSetupHttpClient(
        setup_base_url=BASE_URL,
        setup_handoff_credential=(
            HANDOFF_CREDENTIAL
        ),
    )


def test_client_repr_redacts_handoff_credential() -> None:
    rendered = repr(
        _client()
    )

    assert HANDOFF_CREDENTIAL not in rendered
    assert (
        "setup_handoff_credential=<redacted>"
        in rendered
    )


@pytest.mark.parametrize(
    (
        "kwargs",
        "exception_type",
        "match",
    ),
    (
        (
            {
                "setup_base_url": "",
                "setup_handoff_credential": (
                    HANDOFF_CREDENTIAL
                ),
            },
            ValueError,
            "setup_base_url is required",
        ),
        (
            {
                "setup_base_url": BASE_URL,
                "setup_handoff_credential": "",
            },
            ValueError,
            "setup_handoff_credential is required",
        ),
        (
            {
                "setup_base_url": BASE_URL,
                "setup_handoff_credential": (
                    HANDOFF_CREDENTIAL
                ),
                "timeout_seconds": 0,
            },
            ValueError,
            "timeout_seconds must be greater than zero",
        ),
        (
            {
                "setup_base_url": BASE_URL,
                "setup_handoff_credential": (
                    HANDOFF_CREDENTIAL
                ),
                "timeout_seconds": True,
            },
            ValueError,
            "timeout_seconds must be greater than zero",
        ),
    ),
)
def test_client_rejects_invalid_configuration(
    kwargs,
    exception_type,
    match,
) -> None:
    with pytest.raises(
        exception_type,
        match=match,
    ):
        CustomerSetupHttpClient(
            **kwargs
        )


def test_base_url_trailing_slash_is_normalized(
    monkeypatch,
) -> None:
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
        return _response(
            202,
            json={
                "status": "build_pending",
            },
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    client = CustomerSetupHttpClient(
        setup_base_url=f"{BASE_URL}/",
        setup_handoff_credential=(
            HANDOFF_CREDENTIAL
        ),
    )

    client.provision(
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        )
    )

    assert calls[0][0] == (
        f"{BASE_URL}/customer/setup/provision"
    )


def test_provision_build_pending_202(
    monkeypatch,
) -> None:
    captured = {}

    def fake_post(
        url,
        **kwargs,
    ):
        captured["url"] = url
        captured.update(
            kwargs
        )

        return _response(
            202,
            json={
                "status": "build_pending",
            },
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    result = _client().provision(
        account_fingerprint=(
            f"  {ACCOUNT_FINGERPRINT}  "
        )
    )

    assert result == (
        CustomerSetupProvisioningTransportResult(
            status="build_pending",
        )
    )

    assert captured["url"] == (
        f"{BASE_URL}/customer/setup/provision"
    )
    assert captured["json"] == {
        "account_fingerprint": (
            ACCOUNT_FINGERPRINT
        ),
    }
    assert captured["headers"] == {
        "Authorization": (
            f"Bearer {HANDOFF_CREDENTIAL}"
        ),
    }
    assert captured["timeout"] == 5.0


def test_provision_ready_200(
    monkeypatch,
) -> None:
    def fake_post(
        url,
        **kwargs,
    ):
        del url
        del kwargs

        return _response(
            200,
            json={
                "status": "ready",
                "artifact_sha256": (
                    ARTIFACT_SHA256
                ),
                "artifact_size_bytes": (
                    ARTIFACT_SIZE_BYTES
                ),
            },
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    result = _client().provision(
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        )
    )

    assert result.status == "ready"
    assert (
        result.artifact_sha256
        == ARTIFACT_SHA256
    )
    assert (
        result.artifact_size_bytes
        == ARTIFACT_SIZE_BYTES
    )


def test_provision_rejects_invalid_pending_shape(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: _response(
            202,
            json={
                "status": "build_pending",
                "artifact_sha256": (
                    ARTIFACT_SHA256
                ),
            },
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Invalid build_pending"
        ),
    ):
        _client().provision(
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            )
        )


@pytest.mark.parametrize(
    "payload",
    (
        {
            "status": "ready",
            "artifact_sha256": (
                ARTIFACT_SHA256
            ),
        },
        {
            "status": "ready",
            "artifact_sha256": "bad",
            "artifact_size_bytes": (
                ARTIFACT_SIZE_BYTES
            ),
        },
        {
            "status": "ready",
            "artifact_sha256": (
                ARTIFACT_SHA256
            ),
            "artifact_size_bytes": 0,
        },
        {
            "status": "different",
            "artifact_sha256": (
                ARTIFACT_SHA256
            ),
            "artifact_size_bytes": (
                ARTIFACT_SIZE_BYTES
            ),
        },
    ),
)
def test_provision_invalid_ready_response_fails_closed(
    monkeypatch,
    payload,
) -> None:
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: _response(
            200,
            json=payload,
        ),
    )

    with pytest.raises(
        RuntimeError,
    ):
        _client().provision(
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            )
        )


def test_provision_invalid_json_fails_closed(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: _response(
            200,
            content=b"not-json",
            headers={
                "content-type": "application/json",
            },
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="not valid JSON",
    ):
        _client().provision(
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            )
        )


def test_provision_http_failure_is_not_success(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: _response(
            401,
            json={
                "detail": "unauthorized",
            },
        ),
    )

    with pytest.raises(
        httpx.HTTPStatusError,
    ):
        _client().provision(
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            )
        )


def test_unexpected_success_status_fails_closed(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: _response(
            204,
            content=b"",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Unexpected successful",
    ):
        _client().provision(
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            )
        )


def test_download_package_returns_raw_ex5_bytes(
    monkeypatch,
) -> None:
    captured = {}

    def fake_get(
        url,
        **kwargs,
    ):
        captured["url"] = url
        captured.update(
            kwargs
        )

        return _response(
            200,
            content=ARTIFACT_CONTENT,
            headers={
                "content-type": (
                    "application/octet-stream"
                ),
            },
            method="GET",
            url=url,
        )

    monkeypatch.setattr(
        module.httpx,
        "get",
        fake_get,
    )

    content = _client().download_package()

    assert content == ARTIFACT_CONTENT
    assert captured["url"] == (
        f"{BASE_URL}/customer/setup/package"
    )
    assert captured["headers"] == {
        "Authorization": (
            f"Bearer {HANDOFF_CREDENTIAL}"
        ),
    }
    assert captured["timeout"] == 5.0


def test_download_accepts_content_type_parameters(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        module.httpx,
        "get",
        lambda *args, **kwargs: _response(
            200,
            content=ARTIFACT_CONTENT,
            headers={
                "content-type": (
                    "application/octet-stream; "
                    "charset=binary"
                ),
            },
            method="GET",
        ),
    )

    assert (
        _client().download_package()
        == ARTIFACT_CONTENT
    )


def test_download_http_failure_is_not_success(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        module.httpx,
        "get",
        lambda *args, **kwargs: _response(
            403,
            json={
                "detail": "forbidden",
            },
            method="GET",
        ),
    )

    with pytest.raises(
        httpx.HTTPStatusError,
    ):
        _client().download_package()


def test_download_wrong_content_type_fails_closed(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        module.httpx,
        "get",
        lambda *args, **kwargs: _response(
            200,
            content=ARTIFACT_CONTENT,
            headers={
                "content-type": "text/plain",
            },
            method="GET",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="invalid content type",
    ):
        _client().download_package()


def test_download_empty_package_fails_closed(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        module.httpx,
        "get",
        lambda *args, **kwargs: _response(
            200,
            content=b"",
            headers={
                "content-type": (
                    "application/octet-stream"
                ),
            },
            method="GET",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="response is empty",
    ):
        _client().download_package()


def test_provision_requires_account_fingerprint() -> None:
    with pytest.raises(
        ValueError,
        match="account_fingerprint is required",
    ):
        _client().provision(
            account_fingerprint=" "
        )


def test_owner_has_no_mt5_install_or_polling_ownership(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_http_client.py"
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

    forbidden = (
        "CustomerMT5SetupPreflightService",
        "CustomerMT5EX5InstallerService",
        "time.sleep",
        "asyncio.sleep",
        "MQL5",
        "Experts",
        "MetaTrader5",
        "initialize_empty(",
        "storage_path",
    )

    for token in forbidden:
        assert token not in source


def test_result_build_pending_rejects_metadata() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "build_pending must not contain artifact metadata"
        ),
    ):
        CustomerSetupProvisioningTransportResult(
            status="build_pending",
            artifact_sha256=(
                ARTIFACT_SHA256
            ),
        )

# ===== CAP E: CUSTOMER SETUP CONTINUATION CLIENT =====


def test_cap_e_provision_captures_redacted_continuation(
    monkeypatch,
) -> None:
    continuation_credential = (
        "tdbsc1.cap-e-continuation-secret"
    )

    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: module.httpx.Response(
            202,
            json={
                "status": "build_pending",
                "continuation_credential": (
                    continuation_credential
                ),
            },
        ),
    )

    result = _client().provision(
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        )
    )

    assert result.status == "build_pending"
    assert (
        result.continuation_credential
        == continuation_credential
    )
    assert (
        continuation_credential
        not in repr(result)
    )


def test_cap_e_continue_uses_only_continuation_bearer(
    monkeypatch,
) -> None:
    continuation_credential = (
        "tdbsc1.cap-e-continuation-secret"
    )
    captured = {}

    def fake_post(
        url,
        **kwargs,
    ):
        captured["url"] = url
        captured.update(kwargs)

        return module.httpx.Response(
            200,
            json={
                "status": "ready",
                "artifact_sha256": (
                    ARTIFACT_SHA256
                ),
                "artifact_size_bytes": (
                    ARTIFACT_SIZE_BYTES
                ),
            },
        )

    monkeypatch.setattr(
        module.httpx,
        "post",
        fake_post,
    )

    result = _client().continue_provisioning(
        continuation_credential=(
            continuation_credential
        )
    )

    assert captured["url"] == (
        f"{BASE_URL}/customer/setup/continue"
    )
    assert captured["headers"] == {
        "Authorization": (
            f"Bearer {continuation_credential}"
        ),
    }
    assert "json" not in captured
    assert result.status == "ready"
    assert (
        result.artifact_sha256
        == ARTIFACT_SHA256
    )
    assert (
        result.artifact_size_bytes
        == ARTIFACT_SIZE_BYTES
    )


def test_cap_e_continue_pending_preserves_same_credential(
    monkeypatch,
) -> None:
    continuation_credential = (
        "tdbsc1.cap-e-continuation-secret"
    )

    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: module.httpx.Response(
            202,
            json={
                "status": "build_pending",
                "continuation_credential": (
                    continuation_credential
                ),
            },
        ),
    )

    result = _client().continue_provisioning(
        continuation_credential=(
            continuation_credential
        )
    )

    assert result.status == "build_pending"
    assert (
        result.continuation_credential
        == continuation_credential
    )


def test_cap_e_continue_rejects_credential_change(
    monkeypatch,
) -> None:
    continuation_credential = (
        "tdbsc1.cap-e-continuation-secret"
    )

    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: module.httpx.Response(
            202,
            json={
                "status": "build_pending",
                "continuation_credential": (
                    "tdbsc1.different-secret"
                ),
            },
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="changed continuation credential",
    ):
        _client().continue_provisioning(
            continuation_credential=(
                continuation_credential
            )
        )


def test_cap_e_package_download_uses_continuation_bearer(
    monkeypatch,
) -> None:
    continuation_credential = (
        "tdbsc1.cap-e-continuation-secret"
    )
    captured = {}

    def fake_get(
        url,
        **kwargs,
    ):
        captured["url"] = url
        captured.update(kwargs)

        return module.httpx.Response(
            200,
            headers={
                "content-type": (
                    "application/octet-stream"
                ),
            },
            content=b"cap-e-package",
        )

    monkeypatch.setattr(
        module.httpx,
        "get",
        fake_get,
    )

    content = _client().download_package(
        continuation_credential=(
            continuation_credential
        )
    )

    assert content == b"cap-e-package"
    assert captured["url"] == (
        f"{BASE_URL}/customer/setup/package"
    )
    assert captured["headers"] == {
        "Authorization": (
            f"Bearer {continuation_credential}"
        ),
    }


def test_cap_e_ready_result_rejects_continuation_credential(
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "ready must not contain "
            "continuation_credential"
        ),
    ):
        CustomerSetupProvisioningTransportResult(
            status="ready",
            continuation_credential=(
                "tdbsc1.cap-e-continuation-secret"
            ),
            artifact_sha256=(
                ARTIFACT_SHA256
            ),
            artifact_size_bytes=(
                ARTIFACT_SIZE_BYTES
            ),
        )


# ===== CAP F: PRODUCTION CONTINUATION RESPONSE COMPATIBILITY =====


def test_cap_f_provision_accepts_production_continuation_expiry(
    monkeypatch,
) -> None:
    continuation_credential = (
        "tdbsc1.cap-f-production-continuation"
    )

    continuation_expires_at = (
        "2026-09-04T01:19:27.707380Z"
    )

    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: module.httpx.Response(
            202,
            json={
                "status": "build_pending",
                "continuation_credential": (
                    continuation_credential
                ),
                "continuation_expires_at": (
                    continuation_expires_at
                ),
            },
        ),
    )

    result = _client().provision(
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        )
    )

    assert result.status == "build_pending"

    assert (
        result.continuation_credential
        == continuation_credential
    )

    assert (
        continuation_credential
        not in repr(result)
    )

    assert (
        not hasattr(
            result,
            "continuation_expires_at",
        )
    )


def test_cap_f_provision_rejects_expiry_without_credential(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: module.httpx.Response(
            202,
            json={
                "status": "build_pending",
                "continuation_credential": None,
                "continuation_expires_at": (
                    "2026-09-04T01:19:27.707380Z"
                ),
            },
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Invalid build_pending customer setup "
            "continuation expiry"
        ),
    ):
        _client().provision(
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            )
        )


@pytest.mark.parametrize(
    "invalid_expiry",
    [
        "",
        " 2026-09-04T01:19:27Z",
        123,
    ],
)
def test_cap_f_provision_rejects_invalid_continuation_expiry(
    monkeypatch,
    invalid_expiry,
) -> None:
    monkeypatch.setattr(
        module.httpx,
        "post",
        lambda *args, **kwargs: module.httpx.Response(
            202,
            json={
                "status": "build_pending",
                "continuation_credential": (
                    "tdbsc1.cap-f-production-continuation"
                ),
                "continuation_expires_at": (
                    invalid_expiry
                ),
            },
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Invalid build_pending customer setup "
            "continuation expiry"
        ),
    ):
        _client().provision(
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            )
        )
