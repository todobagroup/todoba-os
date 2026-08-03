from fastapi.testclient import TestClient

from backend.trading.execution.broker_execution_evidence_api import (
    create_broker_execution_evidence_router,
)

from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)


from fastapi import FastAPI


def create_test_app():

    store = BrokerExecutionEvidenceStore()

    app = FastAPI()

    app.include_router(
        create_broker_execution_evidence_router(
            store
        )
    )

    return app, store


def test_broker_execution_evidence_is_stored():

    app, store = create_test_app()

    client = TestClient(
        app
    )

    response = client.post(
        "/broker/evidence",
        json={
            "mission_id": "proof049-001",
            "agent_id": "trusted-agent-001",
            "success": True,
            "retcode": 10009,
            "order_ticket": 922753906,
            "deal_ticket": 1114153808,
            "execution_price": 4038.8,
            "comment": "Request executed",
            "completed_at": "2026-08-04T00:00:00",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "stored"

    assert data["mission_id"] == (
        "proof049-001"
    )

    assert store.size() == 1