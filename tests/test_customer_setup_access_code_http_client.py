from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path
from urllib.error import URLError

import pytest

import backend.commercial.customer_setup_access_code_http_client as client_module
from backend.commercial.customer_setup_access_code_http_client import (
    CustomerSetupAccessCodeHttpClient,
    CustomerSetupAccessCodeTransportResult,
)


SETUP_BASE_URL = (
    "https://setup.todoba.example"
)

ACTIVATION_CODE = (
    "tdbsa."
    + ("1" * 32)
    + "."
    + ("A" * 43)
)

CODE_CHALLENGE = (
    "B" * 43
)

AUTHORIZATION_CODE = (
    "tdbba."
    + ("2" * 32)
    + "."
    + ("C" * 43)
)

EXPIRES_AT = (
    "2026-09-04T16:30:00+00:00"
)


class _FakeResponse:
    def __init__(
        self,
        *,
        status=200,
        payload=None,
        raw_body=None,
    ):
        self.status = status

        if raw_body is not None:
            self._body = raw_body
        else:
            self._body = json.dumps(
                payload
            ).encode(
                "utf-8"
            )

    def __enter__(
        self,
    ):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        del exc_type
        del exc
        del traceback
        return False

    def read(
        self,
    ):
        return self._body


def _success_response(
):
    return _FakeResponse(
        payload={
            "authorization_code": (
                AUTHORIZATION_CODE
            ),
            "expires_at": (
                EXPIRES_AT
            ),
        }
    )


def test_exchange_posts_exact_customer_authority_surface(
    monkeypatch,
) -> None:
    observed = {}

    def fake_urlopen(
        request,
        *,
        timeout,
    ):
        observed[
            "request"
        ] = request

        observed[
            "timeout"
        ] = timeout

        return _success_response()

    monkeypatch.setattr(
        client_module,
        "urlopen",
        fake_urlopen,
    )

    client = (
        CustomerSetupAccessCodeHttpClient(
            setup_base_url=(
                SETUP_BASE_URL
            )
        )
    )

    result = client.exchange(
        activation_code=(
            ACTIVATION_CODE
        ),
        code_challenge_s256=(
            CODE_CHALLENGE
        ),
    )

    request = observed[
        "request"
    ]

    assert (
        request.full_url
        == (
            SETUP_BASE_URL
            + "/customer/setup/access-code/exchange"
        )
    )

    assert (
        request.get_method()
        == "POST"
    )

    assert json.loads(
        request.data.decode(
            "utf-8"
        )
    ) == {
        "activation_code": (
            ACTIVATION_CODE
        ),
        "code_challenge_s256": (
            CODE_CHALLENGE
        ),
    }

    assert (
        observed[
            "timeout"
        ]
        == 10.0
    )

    assert (
        result.authorization_code
        == AUTHORIZATION_CODE
    )

    assert (
        result.expires_at
        == EXPIRES_AT
    )


def test_trailing_base_url_slash_does_not_duplicate_separator(
    monkeypatch,
) -> None:
    observed = {}

    def fake_urlopen(
        request,
        *,
        timeout,
    ):
        del timeout

        observed[
            "url"
        ] = request.full_url

        return _success_response()

    monkeypatch.setattr(
        client_module,
        "urlopen",
        fake_urlopen,
    )

    client = (
        CustomerSetupAccessCodeHttpClient(
            setup_base_url=(
                SETUP_BASE_URL
                + "/"
            )
        )
    )

    client.exchange(
        activation_code=ACTIVATION_CODE,
        code_challenge_s256=(
            CODE_CHALLENGE
        ),
    )

    assert observed[
        "url"
    ] == (
        SETUP_BASE_URL
        + "/customer/setup/access-code/exchange"
    )


def test_response_schema_is_exact(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        client_module,
        "urlopen",
        lambda request, timeout: (
            _FakeResponse(
                payload={
                    "authorization_code": (
                        AUTHORIZATION_CODE
                    ),
                    "expires_at": (
                        EXPIRES_AT
                    ),
                    "customer_id": (
                        "customer-attacker"
                    ),
                }
            )
        ),
    )

    client = (
        CustomerSetupAccessCodeHttpClient(
            setup_base_url=SETUP_BASE_URL
        )
    )

    with pytest.raises(
        RuntimeError,
        match="invalid schema",
    ):
        client.exchange(
            activation_code=ACTIVATION_CODE,
            code_challenge_s256=(
                CODE_CHALLENGE
            ),
        )


def test_non_object_response_is_rejected(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        client_module,
        "urlopen",
        lambda request, timeout: (
            _FakeResponse(
                payload=[
                    AUTHORIZATION_CODE
                ]
            )
        ),
    )

    client = (
        CustomerSetupAccessCodeHttpClient(
            setup_base_url=SETUP_BASE_URL
        )
    )

    with pytest.raises(
        RuntimeError,
        match="invalid schema",
    ):
        client.exchange(
            activation_code=ACTIVATION_CODE,
            code_challenge_s256=(
                CODE_CHALLENGE
            ),
        )


def test_malformed_json_is_rejected_without_secret_leak(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        client_module,
        "urlopen",
        lambda request, timeout: (
            _FakeResponse(
                raw_body=b"{not-json"
            )
        ),
    )

    client = (
        CustomerSetupAccessCodeHttpClient(
            setup_base_url=SETUP_BASE_URL
        )
    )

    with pytest.raises(
        RuntimeError,
        match="invalid schema",
    ) as error:
        client.exchange(
            activation_code=ACTIVATION_CODE,
            code_challenge_s256=(
                CODE_CHALLENGE
            ),
        )

    assert (
        ACTIVATION_CODE
        not in str(
            error.value
        )
    )


def test_transport_error_is_generic_and_does_not_leak_activation_code(
    monkeypatch,
) -> None:
    def fail_urlopen(
        request,
        *,
        timeout,
    ):
        del request
        del timeout

        raise URLError(
            "sensitive network detail"
        )

    monkeypatch.setattr(
        client_module,
        "urlopen",
        fail_urlopen,
    )

    client = (
        CustomerSetupAccessCodeHttpClient(
            setup_base_url=SETUP_BASE_URL
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Customer setup activation "
            "exchange failed"
        ),
    ) as error:
        client.exchange(
            activation_code=ACTIVATION_CODE,
            code_challenge_s256=(
                CODE_CHALLENGE
            ),
        )

    rendered = str(
        error.value
    )

    assert (
        ACTIVATION_CODE
        not in rendered
    )

    assert (
        "sensitive network detail"
        not in rendered
    )


def test_non_200_response_fails_closed(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        client_module,
        "urlopen",
        lambda request, timeout: (
            _FakeResponse(
                status=500,
                payload={
                    "detail": "internal"
                },
            )
        ),
    )

    client = (
        CustomerSetupAccessCodeHttpClient(
            setup_base_url=SETUP_BASE_URL
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Customer setup activation "
            "exchange failed"
        ),
    ):
        client.exchange(
            activation_code=ACTIVATION_CODE,
            code_challenge_s256=(
                CODE_CHALLENGE
            ),
        )


@pytest.mark.parametrize(
    (
        "activation_code",
        "challenge",
    ),
    [
        (
            "",
            CODE_CHALLENGE,
        ),
        (
            " activation-code ",
            CODE_CHALLENGE,
        ),
        (
            ACTIVATION_CODE,
            "",
        ),
        (
            ACTIVATION_CODE,
            " challenge ",
        ),
    ],
)
def test_exchange_rejects_empty_or_non_normalized_customer_input(
    monkeypatch,
    activation_code,
    challenge,
) -> None:
    called = []

    monkeypatch.setattr(
        client_module,
        "urlopen",
        lambda request, timeout: (
            called.append(
                (
                    request,
                    timeout,
                )
            )
        ),
    )

    client = (
        CustomerSetupAccessCodeHttpClient(
            setup_base_url=SETUP_BASE_URL
        )
    )

    with pytest.raises(
        ValueError,
    ):
        client.exchange(
            activation_code=(
                activation_code
            ),
            code_challenge_s256=(
                challenge
            ),
        )

    assert called == []


def test_transport_result_repr_redacts_internal_authorization_code(
) -> None:
    result = (
        CustomerSetupAccessCodeTransportResult(
            authorization_code=(
                AUTHORIZATION_CODE
            ),
            expires_at=(
                EXPIRES_AT
            ),
        )
    )

    rendered = repr(
        result
    )

    assert (
        AUTHORIZATION_CODE
        not in rendered
    )


def test_client_has_exact_public_exchange_surface(
) -> None:
    parameters = inspect.signature(
        CustomerSetupAccessCodeHttpClient.exchange
    ).parameters

    assert set(
        parameters
    ) == {
        "self",
        "activation_code",
        "code_challenge_s256",
    }


def test_owner_has_no_identity_payment_deployment_or_persistence_authority(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_access_code_http_client.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    identifiers = set()
    called_names = set()
    imported_modules = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Name,
        ):
            identifiers.add(
                node.id
            )

        elif isinstance(
            node,
            ast.Attribute,
        ):
            identifiers.add(
                node.attr
            )

        elif isinstance(
            node,
            ast.FunctionDef,
        ):
            for argument in (
                list(
                    node.args.posonlyargs
                )
                + list(
                    node.args.args
                )
                + list(
                    node.args.kwonlyargs
                )
            ):
                identifiers.add(
                    argument.arg
                )

        if isinstance(
            node,
            ast.Call,
        ):
            if isinstance(
                node.func,
                ast.Name,
            ):
                called_names.add(
                    node.func.id
                )

            elif isinstance(
                node.func,
                ast.Attribute,
            ):
                called_names.add(
                    node.func.attr
                )

        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                imported_modules.add(
                    alias.name
                )

        elif (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module is not None
        ):
            imported_modules.add(
                node.module
            )

    forbidden_identifiers = {
        "customer_id",
        "setup_activation_id",
        "deployment_id",
        "payment_id",
        "subscription_id",
    }

    assert forbidden_identifiers.isdisjoint(
        identifiers
    )

    forbidden_actions = {
        "initialize_empty",
        "open_existing",
        "issue",
        "authorize",
        "revoke",
        "grant",
        "register",
        "bind",
    }

    assert forbidden_actions.isdisjoint(
        called_names
    )

    assert (
        "backend.main"
        not in imported_modules
    )

    assert not {
        module
        for module in imported_modules
        if module.startswith(
            "backend.commercial."
        )
    }
