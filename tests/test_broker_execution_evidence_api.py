from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.broker_execution_evidence_api import (
    create_broker_execution_evidence_router,
)
from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)
from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)
from backend.trading.execution.execution_mission_completed_store import (
    ExecutionMissionCompletedStore,
)
from backend.trading.execution.execution_mission_evidence_intake import (
    ExecutionMissionEvidenceIntake,
)
from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
)
from backend.trading.execution.execution_mission_execution_started_store import (
    ExecutionMissionExecutionStartedStore,
)
from backend.trading.execution.execution_mission_failed_store import (
    ExecutionMissionFailedStore,
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


def create_test_app(
    tmp_path: Path,
) -> tuple[
    FastAPI,
    BrokerExecutionEvidenceStore,
    ExecutionMissionEvidencePersistence,
]:
    broker_evidence_store = (
        BrokerExecutionEvidenceStore()
    )

    persistence = ExecutionMissionEvidencePersistence(
        tmp_path
        / "execution_mission_evidence.json"
    )

    intake = ExecutionMissionEvidenceIntake(
        persistence=persistence,
        acknowledgement_store=(
            ExecutionMissionAcknowledgementStore()
        ),
        execution_started_store=(
            ExecutionMissionExecutionStartedStore()
        ),
        completed_store=(
            ExecutionMissionCompletedStore()
        ),
        failed_store=(
            ExecutionMissionFailedStore()
        ),
        broker_evidence_store=(
            broker_evidence_store
        ),
    )

    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    app = FastAPI()

    app.include_router(
        create_broker_execution_evidence_router(
            intake,
            authenticator,
        )
    )

    return (
        app,
        broker_evidence_store,
        persistence,
    )


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


def test_broker_execution_evidence_is_stored(
    tmp_path: Path,
) -> None:
    app, store, persistence = create_test_app(
        tmp_path
    )

    client = TestClient(
        app
    )

    response = client.post(
        "/broker/evidence",
        headers=AUTHENTICATION_HEADERS,
        json=build_payload(),
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "stored",
        "mission_id": "proof049-001",
        "store_size": 1,
    }

    assert persistence.size() == 1
    assert store.size() == 1


def test_broker_execution_evidence_rejects_missing_credentials(
    tmp_path: Path,
) -> None:
    app, store, persistence = create_test_app(
        tmp_path
    )

    client = TestClient(
        app
    )

    response = client.post(
        "/broker/evidence",
        json=build_payload(),
    )

    assert response.status_code == 401
    assert persistence.size() == 0
    assert store.size() == 0


def test_broker_execution_evidence_rejects_wrong_agent_identity(
    tmp_path: Path,
) -> None:
    app, store, persistence = create_test_app(
        tmp_path
    )

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

    assert persistence.size() == 0
    assert store.size() == 0