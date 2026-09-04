from __future__ import annotations

import ast
from pathlib import Path


def _main_source(
) -> str:
    return (
        Path(__file__)
        .resolve()
        .parents[1]
        / "backend"
        / "main.py"
    ).read_text(
        encoding="utf-8"
    )


def test_main_composes_access_code_exchange_chain(
) -> None:
    source = _main_source()

    required = (
        "CustomerSetupAccessCodeStore",
        "CustomerSetupAccessCodeService",
        "CustomerSetupAccessCodeExchangeService",
        "create_customer_setup_access_code_router",
        "customer_setup_access_codes.json",
        "access_code_service.authorize",
        "bootstrap_authorization_service.issue",
        "access_code_exchange_service.exchange",
    )

    for token in required:
        assert token in source


def test_main_runtime_never_initializes_access_code_store(
) -> None:
    source = _main_source()

    assert (
        "access_code_store.initialize_empty()"
        not in source
    )

    assert (
        "customer_setup_access_code_store.initialize_empty()"
        not in source
    )


def test_main_access_code_store_is_required_ready_owner(
) -> None:
    source = _main_source()

    assert (
        '"Customer setup access code store"'
        in source
    )

    assert (
        "access_code_store,"
        in source
    )


def test_main_publishes_access_code_runtime_owners(
) -> None:
    source = _main_source()

    assert (
        "customer_setup_access_code_store ="
        in source
    )

    assert (
        "customer_setup_access_code_service ="
        in source
    )

    assert (
        "customer_setup_access_code_exchange_service ="
        in source
    )


def test_main_has_no_access_code_payment_authority(
) -> None:
    source = _main_source()

    tree = ast.parse(
        source
    )

    access_constructor_keywords = set()

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        func = node.func

        name = None

        if isinstance(
            func,
            ast.Name,
        ):
            name = func.id

        if name not in {
            "CustomerSetupAccessCodeStore",
            "CustomerSetupAccessCodeService",
            "CustomerSetupAccessCodeExchangeService",
            "create_customer_setup_access_code_router",
        }:
            continue

        access_constructor_keywords.update(
            keyword.arg
            for keyword in node.keywords
            if keyword.arg is not None
        )

    forbidden = {
        "payment_id",
        "subscription_id",
        "deployment_id",
        "customer_id",
        "setup_activation_id",
    }

    assert (
        forbidden.intersection(
            access_constructor_keywords
        )
        == set()
    )