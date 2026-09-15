"""
CAP P0 — Payment Isolation / Trading Availability Guard

Regression owner:

A payment production startup failure must remain inside the
commercial/payment boundary and must not abort the shared FastAPI
lifespan before the trading runtime recovery path can start.

Payment remains fail-closed. This test does not weaken payment
authentication, durable-state requirements, or operator authority.
"""

import ast
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
MAIN_PATH = ROOT_DIR / "backend" / "main.py"

SOURCE = MAIN_PATH.read_text(
    encoding="utf-8"
)

TREE = ast.parse(
    SOURCE,
    filename=str(MAIN_PATH),
)


def _lifespan() -> ast.AsyncFunctionDef:
    for node in TREE.body:
        if (
            isinstance(node, ast.AsyncFunctionDef)
            and node.name == "lifespan"
        ):
            return node

    raise AssertionError(
        "backend.main lifespan owner not found."
    )


def _call_name(
    node: ast.Call,
) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id

    if isinstance(node.func, ast.Attribute):
        parts: list[str] = []
        current: ast.AST = node.func

        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value

        if isinstance(current, ast.Name):
            parts.append(current.id)

        if parts:
            return ".".join(
                reversed(parts)
            )

    return None


def test_payment_startup_failure_is_isolated_before_trading_recovery(
) -> None:
    lifespan = _lifespan()

    payment_call_names = {
        "_compose_customer_payment_runtime",
        "_compose_authenticated_vnd_reconciliation_ingress",
    }

    payment_calls = [
        node
        for node in ast.walk(lifespan)
        if (
            isinstance(node, ast.Call)
            and _call_name(node)
            in payment_call_names
        )
    ]

    assert {
        _call_name(node)
        for node in payment_calls
    } == payment_call_names

    isolation_guards = [
        node
        for node in ast.walk(lifespan)
        if isinstance(node, ast.Try)
    ]

    owning_guard = None

    for guard in isolation_guards:
        guarded_calls = {
            _call_name(node)
            for statement in guard.body
            for node in ast.walk(statement)
            if isinstance(node, ast.Call)
        }

        if payment_call_names.issubset(
            guarded_calls
        ):
            owning_guard = guard
            break

    assert owning_guard is not None, (
        "Payment startup composition is not isolated from "
        "the shared Trading lifespan."
    )

    catches_runtime_error = False

    for handler in owning_guard.handlers:
        if (
            isinstance(handler.type, ast.Name)
            and handler.type.id == "RuntimeError"
        ):
            catches_runtime_error = True

            assert not any(
                isinstance(node, ast.Raise)
                for statement in handler.body
                for node in ast.walk(statement)
            ), (
                "Payment startup failure is re-raised and can "
                "still abort Trading startup."
            )

    assert catches_runtime_error, (
        "Payment isolation guard must contain payment "
        "startup RuntimeError inside the Payment boundary."
    )

    trading_recovery_calls = [
        node
        for node in ast.walk(lifespan)
        if (
            isinstance(node, ast.Call)
            and _call_name(node)
            == "execution_mission_record_recovery.restore"
        )
    ]

    assert len(trading_recovery_calls) == 1

    trading_recovery = trading_recovery_calls[0]

    assert owning_guard.end_lineno is not None

    assert (
        trading_recovery.lineno
        > owning_guard.end_lineno
    ), (
        "Trading recovery must remain reachable after "
        "the isolated Payment startup boundary."
    )


def test_payment_runtime_failure_does_not_take_down_broker_state(
    monkeypatch,
) -> None:
    from fastapi.testclient import TestClient

    from backend import main

    deployments = (
        main.customer_deployment_registry.all()
    )

    assert deployments

    deployment = deployments[0]

    secrets = (
        main.customer_deployment_secret_store.get(
            deployment_id=(
                deployment.deployment_id
            )
        )
    )

    assert secrets is not None

    agent_id = deployment.agent_id
    agent_secret = secrets.agent_secret

    account_fingerprint = (
        main.trusted_agent_account_binding_store
        .get_account_fingerprint(
            agent_id=agent_id
        )
    )

    assert account_fingerprint is not None

    def fail_payment_credentials():
        raise RuntimeError(
            "simulated missing commercial operator credentials"
        )

    monkeypatch.setattr(
        main,
        "get_commercial_operator_credentials",
        fail_payment_credentials,
    )

    monkeypatch.setattr(
        main,
        "_authenticated_vnd_reconciliation_ingress_composed",
        False,
    )

    # Setup is a separate production capability with its own durable
    # provisioning contract. CAP P0 isolates only Payment failure from
    # Trading availability, so the test must not require Setup fixtures.
    monkeypatch.setattr(
        main,
        "_compose_customer_setup_runtime",
        lambda app: None,
    )

    with TestClient(
        main.app
    ) as client:
        response = client.post(
            "/broker/state",
            headers={
                "X-TODOBA-Agent-ID": agent_id,
                "Authorization": (
                    f"Bearer {agent_secret}"
                ),
            },
            json={
                "account_fingerprint": (
                    account_fingerprint
                ),
                "equity": 2500.00,
                "open_position_count": 0,
                "pending_order_count": 0,
                "symbol": "XAUUSD",
                "bid": 4400.00,
                "ask": 4400.20,
                "spread_points": 20.0,
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "stored"
