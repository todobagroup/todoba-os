import ast
from pathlib import Path


MAIN_PATH = Path("backend/main.py")
SOURCE = MAIN_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _function(
    name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef:
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


def _calls_named(
    node: ast.AST,
    name: str,
) -> list[ast.Call]:
    calls = []

    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue

        function = child.func

        if (
            isinstance(function, ast.Name)
            and function.id == name
        ):
            calls.append(child)

    return calls


def _keyword_name(
    call: ast.Call,
    keyword_name: str,
) -> str:
    for keyword in call.keywords:
        if keyword.arg != keyword_name:
            continue

        value = keyword.value

        assert isinstance(value, ast.Name)
        return value.id

    raise AssertionError(
        f"Missing keyword: {keyword_name}"
    )


def test_authenticated_ingress_composes_paid_activation_access_code_boundary():
    compose = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    calls = _calls_named(
        compose,
        "create_customer_setup_access_code_issuance_admin_router",
    )

    assert len(calls) == 1

    call = calls[0]

    assert _keyword_name(
        call,
        "commercial_operator_authentication_dependency",
    ) == "commercial_operator_authentication_dependency"

    assert _keyword_name(
        call,
        "access_code_service",
    ) == "customer_setup_access_code_service"


def test_authenticated_ingress_includes_access_code_issuance_router():
    compose = _function(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    source = ast.get_source_segment(
        SOURCE,
        compose,
    )

    assert source is not None

    assert (
        "authenticated_setup_access_code_issuance_router"
        in source
    )

    assert (
        "app.include_router("
        "\n        authenticated_setup_access_code_issuance_router"
        "\n    )"
        in source
    )


def test_setup_runtime_precedes_authenticated_payment_ingress():
    lifespan = _function("lifespan")

    calls = []

    for child in ast.walk(lifespan):
        if not isinstance(child, ast.Call):
            continue

        function = child.func

        if not isinstance(function, ast.Name):
            continue

        if function.id in {
            "_compose_customer_setup_runtime",
            "_compose_customer_payment_runtime",
            "_compose_authenticated_vnd_reconciliation_ingress",
        }:
            calls.append(
                (
                    child.lineno,
                    function.id,
                )
            )

    calls.sort()

    assert [
        name
        for _, name in calls
    ] == [
        "_compose_customer_setup_runtime",
        "_compose_customer_payment_runtime",
        "_compose_authenticated_vnd_reconciliation_ingress",
    ]


def test_production_imports_access_code_issuance_admin_router():
    imported = False

    for node in TREE.body:
        if not isinstance(node, ast.ImportFrom):
            continue

        if (
            node.module
            != (
                "backend.commercial."
                "customer_setup_access_code_issuance_admin_api"
            )
        ):
            continue

        names = {
            alias.name
            for alias in node.names
        }

        if (
            "create_customer_setup_access_code_issuance_admin_router"
            in names
        ):
            imported = True

    assert imported
