import ast
from pathlib import Path


MAIN_PATH = Path("backend/main.py")
SOURCE = MAIN_PATH.read_text(
    encoding="utf-8-sig"
)
TREE = ast.parse(SOURCE)


def _function(name):
    for node in TREE.body:
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == name
        ):
            return node

    raise AssertionError(
        f"Function not found: {name}"
    )


def _calls_named(node, name):
    calls = []

    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue

        if (
            isinstance(child.func, ast.Name)
            and child.func.id == name
        ):
            calls.append(child)

    return calls


def test_authenticated_ingress_composes_manual_activation_boundary():
    compose = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    calls = _calls_named(
        compose,
        "create_customer_manual_commercial_activation_admin_router",
    )

    assert len(calls) == 1


def test_authenticated_ingress_builds_manual_activation_store():
    compose = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    calls = _calls_named(
        compose,
        "CustomerManualCommercialActivationStore",
    )

    assert len(calls) == 1


def test_authenticated_ingress_includes_manual_activation_router():
    compose = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    source = ast.get_source_segment(
        SOURCE,
        compose,
    )

    assert source is not None

    assert (
        "authenticated_manual_commercial_activation_router"
        in source
    )

    assert (
        "customer_registration_service"
        in source
    )

    assert (
        "customer_setup_activation_service"
        in source
    )


def test_production_has_no_manual_payment_authority():
    module = Path(
        "backend/commercial/"
        "customer_manual_commercial_activation_service.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    forbidden = (
        "mark_paid(",
        "settle(",
        "verify_payment(",
        "complete_verified_payment(",
        "payment_intent_service",
        "settlement_service",
    )

    for token in forbidden:
        assert token not in module


def test_main_does_not_initialize_manual_store_directly():
    assert (
        "manual_commercial_activation_store.initialize_empty("
        not in SOURCE
    )
