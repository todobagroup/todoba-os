from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)
from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)
from backend.trading.execution.execution_mission_completed_api import (
    create_execution_mission_completed_router,
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


def build_client(
    tmp_path: Path,
) -> tuple[
    TestClient,
    ExecutionMissionCompletedStore,
    ExecutionMissionEvidencePersistence,
]:
    completed_store = (
        ExecutionMissionCompletedStore()
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
        completed_store=completed_store,
        failed_store=(
            ExecutionMissionFailedStore()
        ),
        broker_evidence_store=(
            BrokerExecutionEvidenceStore()
        ),
    )

    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    app = FastAPI()

    app.include_router(
        create_execution_mission_completed_router(
            intake,
            authenticator,
        )
    )

    return (
        TestClient(app),
        completed_store,
        persistence,
    )


def build_payload(
    agent_id: str = AGENT_ID,
) -> dict[str, object]:
    return {
        "mission_id": "completed-001",
        "agent_id": agent_id,
        "sequence": 1,
        "completed_at": "2026-07-31T00:20:00Z",
    }


def test_execution_mission_completed_api_receives_evidence(
    tmp_path: Path,
) -> None:
    client, store, persistence = build_client(
        tmp_path
    )

    response = client.post(
        "/missions/completed",
        headers=AUTHENTICATION_HEADERS,
        json=build_payload(),
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "completed",
        "mission_id": "completed-001",
        "store_size": 1,
    }

    assert persistence.size() == 1
    assert store.size() == 1

    evidence = store.pop()

    assert evidence is not None
    assert evidence.mission_id == (
        "completed-001"
    )


def test_execution_mission_completed_api_rejects_missing_credentials(
    tmp_path: Path,
) -> None:
    client, store, persistence = build_client(
        tmp_path
    )

    response = client.post(
        "/missions/completed",
        json=build_payload(),
    )

    assert response.status_code == 401
    assert persistence.size() == 0
    assert store.size() == 0


def test_execution_mission_completed_api_rejects_wrong_agent_identity(
    tmp_path: Path,
) -> None:
    client, store, persistence = build_client(
        tmp_path
    )

    response = client.post(
        "/missions/completed",
        headers=AUTHENTICATION_HEADERS,
        json=build_payload(
            agent_id="trusted-agent-999"
        ),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Completion evidence does not belong "
            "to authenticated Agent."
        ),
    }

    assert persistence.size() == 0
    assert store.size() == 0