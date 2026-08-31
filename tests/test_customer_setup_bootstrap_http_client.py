"""
Owner tests for TODOBA Customer Setup Bootstrap HTTP Client.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import httpx
import pytest

from backend.commercial.customer_setup_bootstrap_http_client import (
    CustomerSetupBootstrapHttpClient,
    CustomerSetupBootstrapTransportResult,
)


BASE_URL = "https://api.todobagroup.com"

AUTHORIZATION_CODE = (
    "tdbba."
    + ("1" * 32)
    + "."
    + ("A" * 43)
)

CODE_VERIFIER = (
    "V" * 64
)

LAUNCH_CREDENTIAL = (
    "tdbsl."
    + ("2" * 32)
    + "."
    + ("B" * 43)
)

EXPIRES_AT = (
    "2026-08-31T12:30:00.000000Z"
)

_DEFAULT_PAYLOAD = object()


def _response(
    *,
    status_code: int = 200,
    payload=_DEFAULT_PAYLOAD,
    content_type: str = "application/json",
) -> httpx.Response:
    if payload is _DEFAULT_PAYLOAD:
        payload = {
            "setup_launch_credential": (
                LAUNCH_CREDENTIAL
            ),
            "expires_at": EXPIRES_AT,
        }

    response_kwargs = {}

    if payload is None:
        response_kwargs[
            "content"
        ] = b"null"
    else:
        response_kwargs[
            "json"
        ] = payload

    return httpx.Response(
        status_code=status_code,
        headers={
            "Content-Type": (
                content_type
            )
        },
        request=httpx.Request(
            "POST",
            (
                f"{BASE_URL}"
                "/customer/setup/bootstrap/exchange"
            ),
        ),
        **response_kwargs,
    )


def _client(
    *,
    setup_base_url: str = BASE_URL,
    authorization_code: str = (
        AUTHORIZATION_CODE
    ),
    code_verifier: str = (
        CODE_VERIFIER
    ),
    timeout_seconds: float = 5.0,
) -> CustomerSetupBootstrapHttpClient:
    return CustomerSetupBootstrapHttpClient(
        setup_base_url=(
            setup_base_url
        ),
        authorization_code=(
            authorization_code
        ),
        code_verifier=(
            code_verifier
        ),
        timeout_seconds=(
            timeout_seconds
        ),
    )


def test_exchange_posts_exact_bootstrap_path_and_pkce_body(
    monkeypatch,
) -> None:
    calls = []

    def fake_post(
        url,
        *,
        json,
        headers,
        timeout,
    ):
        calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )

        return _response()

    monkeypatch.setattr(
        httpx,
        "post",
        fake_post,
    )

    result = _client().exchange()

    assert result == (
        CustomerSetupBootstrapTransportResult(
            setup_launch_credential=(
                LAUNCH_CREDENTIAL
            ),
            expires_at=EXPIRES_AT,
        )
    )

    assert calls == [
        {
            "url": (
                f"{BASE_URL}"
                "/customer/setup/bootstrap/exchange"
            ),
            "json": {
                "authorization_code": (
                    AUTHORIZATION_CODE
                ),
                "code_verifier": (
                    CODE_VERIFIER
                ),
            },
            "headers": {
                "Accept": (
                    "application/json"
                ),
            },
            "timeout": 5.0,
        }
    ]


def test_exchange_request_contains_only_pkce_material(
    monkeypatch,
) -> None:
    observed = {}

    def fake_post(
        url,
        **kwargs,
    ):
        observed[
            "url"
        ] = url

        observed.update(
            kwargs
        )

        return _response()

    monkeypatch.setattr(
        httpx,
        "post",
        fake_post,
    )

    _client().exchange()

    assert set(
        observed["json"]
    ) == {
        "authorization_code",
        "code_verifier",
    }

    forbidden_body_fields = {
        "customer_id",
        "deployment_id",
        "agent_id",
        "setup_activation_id",
        "registration_request_id",
        "payment_id",
        "subscription_id",
        "account_fingerprint",
    }

    assert forbidden_body_fields.isdisjoint(
        observed["json"]
    )

    forbidden_transport_kwargs = {
        "data",
        "content",
        "files",
        "params",
    }

    assert forbidden_transport_kwargs.isdisjoint(
        observed
    )


def test_exchange_sends_no_bearer_customer_identity(
    monkeypatch,
) -> None:
    observed = {}

    def fake_post(
        url,
        **kwargs,
    ):
        del url
        observed.update(
            kwargs
        )
        return _response()

    monkeypatch.setattr(
        httpx,
        "post",
        fake_post,
    )

    _client().exchange()

    assert observed[
        "headers"
    ] == {
        "Accept": "application/json",
    }

    assert (
        "Authorization"
        not in observed["headers"]
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
            url
        )
        del kwargs
        return _response()

    monkeypatch.setattr(
        httpx,
        "post",
        fake_post,
    )

    _client(
        setup_base_url=(
            f"{BASE_URL}/"
        )
    ).exchange()

    assert calls == [
        (
            f"{BASE_URL}"
            "/customer/setup/bootstrap/exchange"
        )
    ]


def test_success_accepts_json_content_type_charset(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: (
            _response(
                content_type=(
                    "application/json; "
                    "charset=utf-8"
                )
            )
        ),
    )

    result = _client().exchange()

    assert (
        result.setup_launch_credential
        == LAUNCH_CREDENTIAL
    )

    assert (
        result.expires_at
        == EXPIRES_AT
    )


@pytest.mark.parametrize(
    "status_code",
    (
        201,
        202,
        400,
        401,
        403,
        404,
        409,
        422,
        500,
        503,
    ),
)
def test_non_200_status_fails_closed_without_body_detail(
    monkeypatch,
    status_code,
) -> None:
    secret_server_detail = (
        "internal-secret-detail"
    )

    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: (
            httpx.Response(
                status_code=(
                    status_code
                ),
                headers={
                    "Content-Type": (
                        "application/json"
                    )
                },
                json={
                    "detail": (
                        secret_server_detail
                    )
                },
                request=httpx.Request(
                    "POST",
                    (
                        f"{BASE_URL}"
                        "/customer/setup/bootstrap/exchange"
                    ),
                ),
            )
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Customer setup bootstrap "
            "request was rejected"
        ),
    ) as error:
        _client().exchange()

    rendered = str(
        error.value
    )

    assert (
        secret_server_detail
        not in rendered
    )
    assert (
        AUTHORIZATION_CODE
        not in rendered
    )
    assert (
        CODE_VERIFIER
        not in rendered
    )


def test_http_transport_failure_is_generic(
    monkeypatch,
) -> None:
    def fake_post(
        *args,
        **kwargs,
    ):
        del args
        del kwargs

        raise httpx.ConnectError(
            (
                "transport failure "
                f"{AUTHORIZATION_CODE} "
                f"{CODE_VERIFIER}"
            )
        )

    monkeypatch.setattr(
        httpx,
        "post",
        fake_post,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Customer setup bootstrap "
            "request failed"
        ),
    ) as error:
        _client().exchange()

    rendered = str(
        error.value
    )

    assert (
        AUTHORIZATION_CODE
        not in rendered
    )
    assert (
        CODE_VERIFIER
        not in rendered
    )


@pytest.mark.parametrize(
    "content_type",
    (
        "",
        "text/plain",
        "application/octet-stream",
        "text/html",
    ),
)
def test_non_json_content_type_fails_closed(
    monkeypatch,
    content_type,
) -> None:
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: (
            _response(
                content_type=(
                    content_type
                )
            )
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="invalid content type",
    ):
        _client().exchange()


def test_invalid_json_fails_closed(
    monkeypatch,
) -> None:
    response = httpx.Response(
        status_code=200,
        headers={
            "Content-Type": (
                "application/json"
            )
        },
        content=b"{not-json",
        request=httpx.Request(
            "POST",
            (
                f"{BASE_URL}"
                "/customer/setup/bootstrap/exchange"
            ),
        ),
    )

    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: (
            response
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="not valid JSON",
    ):
        _client().exchange()


@pytest.mark.parametrize(
    "payload",
    (
        [],
        "bad",
        1,
        None,
        {
            "setup_launch_credential": (
                LAUNCH_CREDENTIAL
            ),
        },
        {
            "expires_at": EXPIRES_AT,
        },
        {
            "setup_launch_credential": (
                LAUNCH_CREDENTIAL
            ),
            "expires_at": EXPIRES_AT,
            "customer_id": (
                "must-not-be-here"
            ),
        },
        {
            "setup_launch_credential": (
                LAUNCH_CREDENTIAL
            ),
            "expires_at": EXPIRES_AT,
            "authorization_id": (
                "must-not-be-here"
            ),
        },
    ),
)
def test_invalid_response_shape_fails_closed(
    monkeypatch,
    payload,
) -> None:
    response_kwargs = {}

    if payload is None:
        response_kwargs[
            "content"
        ] = b"null"
    else:
        response_kwargs[
            "json"
        ] = payload

    response = httpx.Response(
        status_code=200,
        headers={
            "Content-Type": (
                "application/json"
            )
        },
        request=httpx.Request(
            "POST",
            (
                f"{BASE_URL}"
                "/customer/setup/bootstrap/exchange"
            ),
        ),
        **response_kwargs,
    )

    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: (
            response
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="invalid schema",
    ):
        _client().exchange()


@pytest.mark.parametrize(
    "setup_launch_credential",
    (
        "",
        " ",
        " credential",
        "credential ",
        123,
        None,
    ),
)
def test_invalid_launch_credential_fails_closed(
    monkeypatch,
    setup_launch_credential,
) -> None:
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: (
            _response(
                payload={
                    "setup_launch_credential": (
                        setup_launch_credential
                    ),
                    "expires_at": (
                        EXPIRES_AT
                    ),
                }
            )
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="invalid schema",
    ):
        _client().exchange()


@pytest.mark.parametrize(
    "expires_at",
    (
        "",
        " ",
        " expiry",
        "expiry ",
        123,
        None,
    ),
)
def test_invalid_expiry_fails_closed(
    monkeypatch,
    expires_at,
) -> None:
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: (
            _response(
                payload={
                    "setup_launch_credential": (
                        LAUNCH_CREDENTIAL
                    ),
                    "expires_at": (
                        expires_at
                    ),
                }
            )
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="invalid schema",
    ):
        _client().exchange()


def test_client_repr_redacts_bootstrap_secrets(
) -> None:
    rendered = repr(
        _client()
    )

    assert (
        AUTHORIZATION_CODE
        not in rendered
    )
    assert (
        CODE_VERIFIER
        not in rendered
    )

    assert (
        "authorization_code=<redacted>"
        in rendered
    )
    assert (
        "code_verifier=<redacted>"
        in rendered
    )


def test_result_repr_redacts_launch_credential(
) -> None:
    result = (
        CustomerSetupBootstrapTransportResult(
            setup_launch_credential=(
                LAUNCH_CREDENTIAL
            ),
            expires_at=EXPIRES_AT,
        )
    )

    rendered = repr(
        result
    )

    assert (
        LAUNCH_CREDENTIAL
        not in rendered
    )
    assert (
        EXPIRES_AT
        in rendered
    )


@pytest.mark.parametrize(
    "setup_base_url",
    (
        "",
        " ",
        "api.todobagroup.com",
        "ftp://api.todobagroup.com",
        "https:///missing-host",
        (
            "https://user:secret@"
            "api.todobagroup.com"
        ),
        (
            "https://api.todobagroup.com/"
            "unexpected/path"
        ),
        (
            "https://api.todobagroup.com"
            "?query=1"
        ),
        (
            "https://api.todobagroup.com"
            "#fragment"
        ),
    ),
)
def test_invalid_base_url_is_rejected(
    setup_base_url,
) -> None:
    with pytest.raises(
        ValueError,
    ):
        _client(
            setup_base_url=(
                setup_base_url
            )
        )


def test_non_string_base_url_is_rejected(
) -> None:
    with pytest.raises(
        TypeError,
        match="setup_base_url must be str",
    ):
        _client(
            setup_base_url=123
        )


@pytest.mark.parametrize(
    "authorization_code",
    (
        "",
        " ",
        " code",
        "code ",
    ),
)
def test_invalid_authorization_code_is_rejected(
    authorization_code,
) -> None:
    with pytest.raises(
        ValueError,
    ):
        _client(
            authorization_code=(
                authorization_code
            )
        )


def test_non_string_authorization_code_is_rejected(
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "authorization_code "
            "must be str"
        ),
    ):
        _client(
            authorization_code=123
        )


@pytest.mark.parametrize(
    "code_verifier",
    (
        "",
        " ",
        " verifier",
        "verifier ",
    ),
)
def test_invalid_code_verifier_is_rejected(
    code_verifier,
) -> None:
    with pytest.raises(
        ValueError,
    ):
        _client(
            code_verifier=(
                code_verifier
            )
        )


def test_non_string_code_verifier_is_rejected(
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "code_verifier must be str"
        ),
    ):
        _client(
            code_verifier=123
        )


@pytest.mark.parametrize(
    "timeout_seconds",
    (
        0,
        -1,
        float("inf"),
        float("-inf"),
        float("nan"),
    ),
)
def test_invalid_timeout_value_is_rejected(
    timeout_seconds,
) -> None:
    with pytest.raises(
        ValueError,
    ):
        _client(
            timeout_seconds=(
                timeout_seconds
            )
        )


@pytest.mark.parametrize(
    "timeout_seconds",
    (
        True,
        False,
        "5",
        None,
    ),
)
def test_invalid_timeout_type_is_rejected(
    timeout_seconds,
) -> None:
    with pytest.raises(
        TypeError,
    ):
        _client(
            timeout_seconds=(
                timeout_seconds
            )
        )


def test_exchange_signature_accepts_no_customer_input(
) -> None:
    parameters = (
        inspect.signature(
            CustomerSetupBootstrapHttpClient.exchange
        ).parameters
    )

    assert set(
        parameters
    ) == {
        "self",
    }


def test_constructor_surface_is_transport_only(
) -> None:
    parameters = (
        inspect.signature(
            CustomerSetupBootstrapHttpClient.__init__
        ).parameters
    )

    assert set(
        parameters
    ) == {
        "self",
        "setup_base_url",
        "authorization_code",
        "code_verifier",
        "timeout_seconds",
    }


def test_owner_has_no_forbidden_commercial_or_mt5_authority(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_bootstrap_http_client.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = __import__(
        "ast"
    ).parse(
        source
    )

    if (
        tree.body
        and isinstance(
            tree.body[0],
            __import__("ast").Expr,
        )
        and isinstance(
            tree.body[0].value,
            __import__("ast").Constant,
        )
        and isinstance(
            tree.body[0].value.value,
            str,
        )
    ):
        start = tree.body[0].lineno - 1
        end = tree.body[0].end_lineno

        lines = source.splitlines(
            keepends=True
        )

        source = "".join(
            lines[:start]
            + lines[end:]
        )

    forbidden_tokens = (
        "customer_id",
        "deployment_id",
        "agent_id",
        "account_fingerprint",
        "setup_activation_id",
        "registration_request_id",
        "payment_id",
        "subscription_id",
        "CustomerSetupBootstrapAuthorizationService",
        "CustomerSetupBootstrapAuthorizationStore",
        "CustomerSetupBootstrapLaunchGrantService",
        "CustomerSetupLaunchCredentialService",
        "CustomerSetupLaunchCredentialStore",
        "CustomerSetupLauncher",
        "CustomerSetupEntryHttpClient",
        "CustomerSetupHttpClient",
        "CustomerMT5",
        "MetaTrader",
        "initialize_empty(",
        "open_existing(",
        "os.environ",
        "backend.config",
        "TODOBA_CLOUD_BASE_URL",
        "package_path",
    )

    for token in forbidden_tokens:
        assert token not in source
