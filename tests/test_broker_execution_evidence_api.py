from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.broker_execution_evidence_api import (
    create_broker_execution_evidence_router,
)
from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "test-trusted-agent-secret"

AUTHENTICATION_HEADERS = {
    "X-TODOBA-Agent-ID": AGENT_ID,
    "Authorization": f"Bearer {AGENT_SECRET}",
}


def create_test_app():
    store = BrokerExecutionEvidenceStore()

    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    app = FastAPI()

    app.include_router(
        create_broker_execution_evidence_router(
            store,
            authenticator,
        )
    )

    return app, store


def build_payload(
    agent_id: str = AGENT_ID,
) -> dict[str, object]:
    return {
        "mission_id": "proof049-001",
        "agent_id": agent_id,
        "success": True,
        "retcode": 10009,
        "order_ticket": 922753906,
        "deal_ticket": 1114153808,
        "execution_price": 4038.8,
        "comment": "Request executed",
        "completed_at": "2026-08-04T00:00:00",
    }


def test_broker_execution_evidence_is_stored() -> None:
    app, store = create_test_app()

    client = TestClient(
        app
    )

    response = client.post(
        "/broker/evidence",
        headers=AUTHENTICATION_HEADERS,
        json=build_payload(),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "stored"
    assert data["mission_id"] == "proof049-001"
    assert store.size() == 1


def test_broker_execution_evidence_rejects_missing_credentials() -> None:
    app, store = create_test_app()

    client = TestClient(
        app
    )

    response = client.post(
        "/broker/evidence",
        json=build_payload(),
    )

    assert response.status_code == 401
    assert store.size() == 0


def test_broker_execution_evidence_rejects_wrong_agent_identity() -> None:
    app, store = create_test_app()

    client = TestClient(
        app
    )

    response = client.post(
        "/broker/evidence",
        headers=AUTHENTICATION_HEADERS,
        json=build_payload(
            agent_id="trusted-agent-999"
        ),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Broker execution evidence does not belong "
            "to authenticated Agent."
        ),
    }
    assert store.size() == 0