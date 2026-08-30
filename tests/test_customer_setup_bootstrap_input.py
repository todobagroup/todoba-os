"""
Owner tests for TODOBA Customer Setup Bootstrap Input.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from backend.commercial.customer_setup_bootstrap_input import (
    CustomerSetupBootstrapInput,
)


BASE_URL = "https://api.todobagroup.com"

LAUNCH_CREDENTIAL = (
    "tdbsl."
    + ("1" * 32)
    + "."
    + ("A" * 43)
)


def _bootstrap(
    *,
    setup_base_url=BASE_URL,
    setup_launch_credential=(
        LAUNCH_CREDENTIAL
    ),
) -> CustomerSetupBootstrapInput:
    return CustomerSetupBootstrapInput(
        setup_base_url=(
            setup_base_url
        ),
        setup_launch_credential=(
            setup_launch_credential
        ),
    )


def test_bootstrap_input_preserves_required_values(
) -> None:
    bootstrap = _bootstrap()

    assert (
        bootstrap.setup_base_url
        == BASE_URL
    )

    assert (
        bootstrap.setup_launch_credential
        == LAUNCH_CREDENTIAL
    )


def test_trailing_base_url_slash_is_normalized(
) -> None:
    bootstrap = _bootstrap(
        setup_base_url=(
            f"{BASE_URL}/"
        )
    )

    assert (
        bootstrap.setup_base_url
        == BASE_URL
    )


def test_outer_base_url_whitespace_is_normalized(
) -> None:
    bootstrap = _bootstrap(
        setup_base_url=(
            f"  {BASE_URL}/  "
        )
    )

    assert (
        bootstrap.setup_base_url
        == BASE_URL
    )


@pytest.mark.parametrize(
    "setup_base_url",
    (
        "",
        " ",
        "api.todobagroup.com",
        "ftp://api.todobagroup.com",
        "file:///tmp/todoba",
    ),
)
def test_invalid_base_url_is_rejected(
    setup_base_url,
) -> None:
    with pytest.raises(
        ValueError,
    ):
        _bootstrap(
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
        _bootstrap(
            setup_base_url=123
        )


@pytest.mark.parametrize(
    "setup_base_url",
    (
        "https://user@api.todobagroup.com",
        "https://user:pass@api.todobagroup.com",
    ),
)
def test_base_url_user_info_is_rejected(
    setup_base_url,
) -> None:
    with pytest.raises(
        ValueError,
        match="must not contain user info",
    ):
        _bootstrap(
            setup_base_url=(
                setup_base_url
            )
        )


@pytest.mark.parametrize(
    "setup_base_url",
    (
        (
            "https://api.todobagroup.com"
            "?customer=1"
        ),
        (
            "https://api.todobagroup.com"
            "#fragment"
        ),
    ),
)
def test_base_url_query_or_fragment_is_rejected(
    setup_base_url,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "must not contain query or fragment"
        ),
    ):
        _bootstrap(
            setup_base_url=(
                setup_base_url
            )
        )


@pytest.mark.parametrize(
    "setup_base_url",
    (
        (
            "https://api.todobagroup.com"
            "/customer"
        ),
        (
            "https://api.todobagroup.com"
            "/customer/setup"
        ),
    ),
)
def test_base_url_path_is_rejected(
    setup_base_url,
) -> None:
    with pytest.raises(
        ValueError,
        match="must not contain a path",
    ):
        _bootstrap(
            setup_base_url=(
                setup_base_url
            )
        )


@pytest.mark.parametrize(
    "credential",
    (
        "",
        " ",
        " credential",
        "credential ",
        "\tcredential",
        "credential\n",
    ),
)
def test_invalid_launch_credential_is_rejected(
    credential,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "setup_launch_credential is invalid"
        ),
    ):
        _bootstrap(
            setup_launch_credential=(
                credential
            )
        )


def test_non_string_launch_credential_is_rejected(
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "setup_launch_credential "
            "must be str"
        ),
    ):
        _bootstrap(
            setup_launch_credential=123
        )


def test_repr_redacts_launch_credential(
) -> None:
    bootstrap = _bootstrap()

    rendered = repr(
        bootstrap
    )

    assert (
        LAUNCH_CREDENTIAL
        not in rendered
    )

    assert (
        BASE_URL
        in rendered
    )


def test_bootstrap_input_is_immutable(
) -> None:
    bootstrap = _bootstrap()

    with pytest.raises(
        FrozenInstanceError,
    ):
        bootstrap.setup_base_url = (
            "https://example.com"
        )


def test_bootstrap_input_uses_slots(
) -> None:
    bootstrap = _bootstrap()

    assert not hasattr(
        bootstrap,
        "__dict__",
    )


def test_owner_import_surface_is_stdlib_only(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_bootstrap_input.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_roots = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                imported_roots.add(
                    alias.name.split(
                        ".",
                        1,
                    )[0]
                )

        if isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module:
                imported_roots.add(
                    node.module.split(
                        ".",
                        1,
                    )[0]
                )

    assert imported_roots <= {
        "__future__",
        "dataclasses",
        "urllib",
    }


def test_owner_has_no_external_acquisition_or_transport(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_bootstrap_input.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    forbidden_import_roots = {
        "argparse",
        "httpx",
        "requests",
        "tkinter",
        "MetaTrader5",
        "os",
        "sys",
        "pathlib",
        "json",
    }

    imported_roots = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                imported_roots.add(
                    alias.name.split(
                        ".",
                        1,
                    )[0]
                )

        if isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module:
                imported_roots.add(
                    node.module.split(
                        ".",
                        1,
                    )[0]
                )

    assert forbidden_import_roots.isdisjoint(
        imported_roots
    )


def test_owner_defines_no_io_or_business_methods(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_bootstrap_input.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    function_names = {
        node.name
        for node in ast.walk(
            tree
        )
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }

    forbidden_methods = {
        "read",
        "load",
        "open",
        "save",
        "write",
        "exchange",
        "issue",
        "authorize",
        "provision",
        "download",
        "install",
        "run",
        "main",
    }

    assert forbidden_methods.isdisjoint(
        function_names
    )


def test_owner_contains_only_bootstrap_fields(
) -> None:
    bootstrap = _bootstrap()

    field_names = {
        field.name
        for field in __import__(
            "dataclasses"
        ).fields(
            bootstrap
        )
    }

    assert field_names == {
        "setup_base_url",
        "setup_launch_credential",
    }


def test_bootstrap_input_contains_no_commercial_identity(
) -> None:
    bootstrap = _bootstrap()

    for forbidden_name in (
        "customer_id",
        "deployment_id",
        "agent_id",
        "account_fingerprint",
        "registration_request_id",
        "grant_request_id",
        "handoff_credential",
        "package_path",
    ):
        assert not hasattr(
            bootstrap,
            forbidden_name,
        )