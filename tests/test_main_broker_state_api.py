"""
TODOBA Main Broker State API Tests

Proof:

backend.main
->
POST /broker/state
->
Trusted Agent authentication
->
authoritative account binding check
->
shared BrokerStateStore
"""

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault(
    "TODOBA_TRUSTED_AGENT_SECRET",
    "proof-main-broker-state-secret",
)

os.environ.setdefault(
    "TODOBA_EXECUTOR_SECRET",
    "proof-main-executor-secret",
)

from backend import main


def test_main_app_contains_broker_state_api(
    monkeypatch,
):
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
            "X-TODOBA-Agent-ID": (
                main.TODOBA_TRUSTED_AGENT_ID
            ),
            "Authorization": (
                "Bearer "
                + main.TODOBA_TRUSTED_AGENT_SECRET
            ),
        },
        json={
            "account_fingerprint": (
                main.TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT
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
            main.TODOBA_TRUSTED_AGENT_ID,
            main.TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT,
        )
    ]

    assert response.json() == {
        "status": "stored",
        "account_fingerprint": (
            main.TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT
        ),
        "symbol": "XAUUSD",
    }

    stored = main.broker_state_store.get(
        account_fingerprint=(
            main.TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT
        ),
        symbol="XAUUSD",
    )

    assert stored is not None
    assert stored.equity == 2491.52
    assert stored.open_position_count == 5
    assert stored.pending_order_count == 3