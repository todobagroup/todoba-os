"""
P8F13C-1 — payment rail startup isolation.

A PayPal-specific RuntimeError may disable PayPal, but it must
not prevent independent VND production composition.

Shared/common Payment startup failure may still be isolated
from Trading availability by the outer payment boundary.
"""

from __future__ import annotations

import ast
from pathlib import Path


MAIN_PATH = Path("backend/main.py")
SOURCE = MAIN_PATH.read_text(
    encoding="utf-8-sig"
)
TREE = ast.parse(SOURCE)


def _lifespan() -> ast.AsyncFunctionDef:
    for node in TREE.body:
        if (
            isinstance(
                node,
                ast.AsyncFunctionDef,
            )
            and node.name == "lifespan"
        ):
            return node

    raise AssertionError(
        "backend.main lifespan owner not found."
    )


def _call_name(
    call: ast.Call,
) -> str | None:
    func = call.func

    if isinstance(
        func,
        ast.Name,
    ):
        return func.id

    if isinstance(
        func,
        ast.Attribute,
    ):
        parts = []
        current = func

        while isinstance(
            current,
            ast.Attribute,
        ):
            parts.append(
                current.attr
            )
            current = current.value

        if isinstance(
            current,
            ast.Name,
        ):
            parts.append(
                current.id
            )

        return ".".join(
            reversed(parts)
        )

    return None


def _guarded_calls(
    guard: ast.Try,
) -> set[str]:
    return {
        name
        for statement in guard.body
        for node in ast.walk(
            statement
        )
        if isinstance(
            node,
            ast.Call,
        )
        for name in [
            _call_name(node)
        ]
        if name is not None
    }


def _runtime_error_guard_for(
    lifespan: ast.AsyncFunctionDef,
    call_name: str,
) -> ast.Try:
    matches = []

    for node in ast.walk(
        lifespan
    ):
        if not isinstance(
            node,
            ast.Try,
        ):
            continue

        if call_name not in _guarded_calls(
            node
        ):
            continue

        catches_runtime_error = any(
            isinstance(
                handler.type,
                ast.Name,
            )
            and handler.type.id
            == "RuntimeError"
            for handler in node.handlers
        )

        if catches_runtime_error:
            matches.append(
                node
            )

    assert matches, (
        f"{call_name} must have a RuntimeError "
        "startup isolation boundary."
    )

    # Select the narrowest owner. This prevents an outer shared
    # payment guard from being mistaken for the rail-specific guard.
    return min(
        matches,
        key=lambda node: (
            (node.end_lineno or node.lineno)
            - node.lineno
        ),
    )


def _single_call(
    lifespan: ast.AsyncFunctionDef,
    call_name: str,
) -> ast.Call:
    calls = [
        node
        for node in ast.walk(
            lifespan
        )
        if (
            isinstance(
                node,
                ast.Call,
            )
            and _call_name(node)
            == call_name
        )
    ]

    assert len(calls) == 1, (
        f"Expected exactly one {call_name} call."
    )

    return calls[0]


def test_paypal_rail_guards_do_not_own_vnd_composers():
    lifespan = _lifespan()

    paypal_capture = (
        "_compose_customer_paypal_verified_capture_ingress"
    )
    paypal_initiation = (
        "_compose_customer_paypal_payment_initiation_runtime"
    )

    vnd_calls = {
        "_compose_authenticated_vnd_reconciliation_ingress",
        "_compose_customer_vnd_payment_initiation_runtime",
    }

    capture_guard = _runtime_error_guard_for(
        lifespan,
        paypal_capture,
    )

    initiation_guard = _runtime_error_guard_for(
        lifespan,
        paypal_initiation,
    )

    assert not (
        _guarded_calls(
            capture_guard
        )
        & vnd_calls
    ), (
        "PayPal capture startup failure can prevent "
        "VND composition."
    )

    assert not (
        _guarded_calls(
            initiation_guard
        )
        & vnd_calls
    ), (
        "PayPal initiation startup failure can prevent "
        "VND composition."
    )


def test_vnd_reconciliation_runs_after_paypal_capture_guard():
    lifespan = _lifespan()

    guard = _runtime_error_guard_for(
        lifespan,
        "_compose_customer_paypal_verified_capture_ingress",
    )

    reconciliation = _single_call(
        lifespan,
        "_compose_authenticated_vnd_reconciliation_ingress",
    )

    assert guard.end_lineno is not None

    assert (
        reconciliation.lineno
        > guard.end_lineno
    ), (
        "VND reconciliation must remain reachable after "
        "PayPal capture startup isolation."
    )


def test_vnd_initiation_runs_after_paypal_initiation_guard():
    lifespan = _lifespan()

    guard = _runtime_error_guard_for(
        lifespan,
        "_compose_customer_paypal_payment_initiation_runtime",
    )

    vnd_initiation = _single_call(
        lifespan,
        "_compose_customer_vnd_payment_initiation_runtime",
    )

    assert guard.end_lineno is not None

    assert (
        vnd_initiation.lineno
        > guard.end_lineno
    ), (
        "VND initiation must remain reachable after "
        "PayPal initiation startup isolation."
    )
