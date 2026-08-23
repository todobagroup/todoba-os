"""
TODOBA Main Broker State API Tests

Proof:

backend.main
->
commercial customer deployment runtime projection
->
Trusted Agent authentication
->
authoritative account binding check
->
shared BrokerStateStore
"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend import main


def test_main_app_contains_broker_state_api(
    monkeypatch,
):
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

    target = (
        main.execution_target_registry.get(
            agent_id=agent_id
        )
    )

    assert target is not None

    assert (
        target.account_fingerprint
        == account_fingerprint
    )

    binding_calls: list[
        tuple[str, str]
    ] = []

    def require_binding(
        *,
        agent_id: str,
        account_fingerprint: str,
    ) -> str:
        binding_calls.append(
            (
                agent_id,
                account_fingerprint,
            )
        )

        return account_fingerprint

    monkeypatch.setattr(
        main.trusted_agent_account_binding_guard,
        "require_binding",
        require_binding,
    )

    client = TestClient(
        main.app
    )

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
            "equity": 2491.52,
            "open_position_count": 5,
            "pending_order_count": 3,
            "symbol": "XAUUSD",
            "bid": 4397.96,
            "ask": 4398.22,
            "spread_points": 26.0,
        },
    )

    assert response.status_code == 200

    assert binding_calls == [
        (
            agent_id,
            account_fingerprint,
        )
    ]

    assert response.json() == {
        "status": "stored",
        "account_fingerprint": (
            account_fingerprint
        ),
        "symbol": "XAUUSD",
    }

    stored = main.broker_state_store.get(
        account_fingerprint=(
            account_fingerprint
        ),
        symbol="XAUUSD",
    )

    assert stored is not None
    assert stored.equity == 2491.52
    assert stored.open_position_count == 5
    assert stored.pending_order_count == 3
