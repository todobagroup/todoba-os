import ast
from pathlib import Path


MAIN_PATH = (
    Path(__file__)
    .resolve()
    .parents[1]
    / "backend"
    / "main.py"
)

SOURCE = MAIN_PATH.read_text(
    encoding="utf-8-sig"
)

TREE = ast.parse(
    SOURCE,
    filename=str(MAIN_PATH),
)


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
        f"{name}() is missing."
    )


def _called_names(node):
    names = set()

    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue

        func = child.func

        if isinstance(func, ast.Name):
            names.add(func.id)

        elif isinstance(func, ast.Attribute):
            names.add(func.attr)

    return names


def test_payment_runtime_remains_state_composition_only():
    payment_runtime = _function(
        "_compose_customer_payment_runtime"
    )

    source = ast.get_source_segment(
        SOURCE,
        payment_runtime,
    )

    assert source is not None

    forbidden = (
        "get_commercial_operator_credentials",
        "CommercialOperatorAuthenticator",
        "create_commercial_operator_authentication_dependency",
        "CustomerVndBankReconciliationService",
        "create_customer_vnd_bank_reconciliation_admin_router",
        "include_router(",
        "operator_id",
    )

    for token in forbidden:
        assert token not in source


def test_authenticated_vnd_ingress_has_dedicated_composition_owner():
    ingress = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    calls = _called_names(
        ingress
    )

    required = {
        "get_commercial_operator_credentials",
        "CommercialOperatorAuthenticator",
        "create_commercial_operator_authentication_dependency",
        "CustomerVndBankReconciliationService",
        "create_customer_vnd_bank_reconciliation_admin_router",
        "include_router",
    }

    missing = required - calls

    assert not missing, (
        f"Missing authenticated VND ingress composition: "
        f"{sorted(missing)}"
    )


def test_authenticated_vnd_ingress_remains_composition_only():
    ingress = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    calls = _called_names(
        ingress
    )

    forbidden = {
        "confirm",
        "publish",
        "receive",
        "build_assertion",
        "verify_payment",
        "settle",
        "mark_paid",
        "activate",
        "activate_from_settlement",
        "complete_verified_payment",
        "capture",
    }

    bad = calls & forbidden

    assert not bad, (
        f"Ingress composition gained payment authority: "
        f"{sorted(bad)}"
    )


def test_authenticated_vnd_ingress_uses_server_owned_payment_state():
    ingress = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    source = ast.get_source_segment(
        SOURCE,
        ingress,
    )

    assert source is not None

    required = (
        "customer_vnd_bank_reconciliation_store",
        "customer_commercial_order_store",
        "customer_payment_intent_store",
    )

    for token in required:
        assert token in source

    forbidden = (
        "initialize_empty(",
        "CustomerCommercialOrderStore(",
        "CustomerPaymentIntentStore(",
        "CustomerVndBankReconciliationStore(",
    )

    for token in forbidden:
        assert token not in source


def test_lifespan_composes_vnd_ingress_after_payment_runtime():
    lifespan = _function(
        "lifespan"
    )

    ordered_calls = []

    for child in ast.walk(lifespan):
        if not isinstance(child, ast.Call):
            continue

        func = child.func

        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        else:
            continue

        ordered_calls.append(
            (
                child.lineno,
                child.col_offset,
                name,
            )
        )

    ordered_calls.sort()

    call_names = [
        name
        for _, _, name in ordered_calls
    ]

    assert (
        "_compose_customer_payment_runtime"
        in call_names
    )

    assert (
        "_compose_authenticated_vnd_reconciliation_ingress"
        in call_names
    )

    payment_index = call_names.index(
        "_compose_customer_payment_runtime"
    )

    ingress_index = call_names.index(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    assert payment_index < ingress_index


def test_authenticated_vnd_ingress_is_idempotently_guarded():
    ingress = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    source = ast.get_source_segment(
        SOURCE,
        ingress,
    )

    assert source is not None

    assert (
        "_authenticated_vnd_reconciliation_ingress_composed"
        in source
    )

    assert (
        "if _authenticated_vnd_reconciliation_ingress_composed"
        in source
    )

    assert (
        "_authenticated_vnd_reconciliation_ingress_composed = True"
        in source
    )



def test_main_imports_authenticated_vnd_ingress_owners():
    imported_names = set()

    for node in TREE.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(
                    alias.asname or alias.name
                )

    required = {
        "get_commercial_operator_credentials",
        "CommercialOperatorAuthenticator",
        "create_commercial_operator_authentication_dependency",
        "CustomerVndBankReconciliationService",
        "create_customer_vnd_bank_reconciliation_admin_router",
    }

    missing = required - imported_names

    assert not missing, (
        f"Missing P8D1 imports: {sorted(missing)}"
    )
