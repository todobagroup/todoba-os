import ast
from pathlib import Path


MAIN_PATH = Path("backend/main.py")


def _source():
    return MAIN_PATH.read_text(
        encoding="utf-8-sig"
    )


def _tree():
    return ast.parse(
        _source()
    )


def _function(name):
    for node in _tree().body:
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            if node.name == name:
                return node

    raise AssertionError(
        f"Function not found: {name}"
    )


def _call_name(node):
    if isinstance(
        node.func,
        ast.Name,
    ):
        return node.func.id

    return None


def _guard_for(
    lifespan,
    call_name,
):
    matching = []

    for node in ast.walk(
        lifespan
    ):
        if not isinstance(
            node,
            ast.Try,
        ):
            continue

        calls = {
            _call_name(child)
            for statement in node.body
            for child in ast.walk(
                statement
            )
            if isinstance(
                child,
                ast.Call,
            )
        }

        if call_name in calls:
            matching.append(
                node
            )

    assert len(
        matching
    ) == 1

    return matching[0]


def test_capture_execution_has_dedicated_composer():
    assert _function(
        "_compose_customer_paypal_capture_execution_runtime"
    )


def test_capture_execution_has_own_runtime_error_guard():
    lifespan = _function(
        "lifespan"
    )

    guard = _guard_for(
        lifespan,
        "_compose_customer_paypal_capture_execution_runtime",
    )

    calls = {
        _call_name(child)
        for statement in guard.body
        for child in ast.walk(
            statement
        )
        if isinstance(
            child,
            ast.Call,
        )
    }

    assert calls == {
        "_compose_customer_paypal_capture_execution_runtime",
    }


def test_vnd_initiation_remains_after_capture_execution_guard():
    lifespan = _function(
        "lifespan"
    )

    guard = _guard_for(
        lifespan,
        "_compose_customer_paypal_capture_execution_runtime",
    )

    vnd_calls = [
        node
        for node in ast.walk(
            lifespan
        )
        if (
            isinstance(
                node,
                ast.Call,
            )
            and _call_name(
                node
            )
            == "_compose_customer_vnd_payment_initiation_runtime"
        )
    ]

    assert len(
        vnd_calls
    ) == 1

    assert (
        guard.end_lineno
        is not None
    )

    assert (
        vnd_calls[0].lineno
        > guard.end_lineno
    )


def test_capture_route_is_customer_authenticated_in_composer():
    source = _source()

    assert (
        "create_customer_paypal_capture_execution_router"
        in source
    )

    assert (
        "customer_authentication_dependency"
        in source
    )
