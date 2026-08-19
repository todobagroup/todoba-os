import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)
from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_acknowledgement_api import (
    create_execution_mission_acknowledgement_router,
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
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


MISSION_ID = "mission-001"
AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "test-trusted-agent-secret"

AUTHENTICATION_HEADERS = {
    "X-TODOBA-Agent-ID": AGENT_ID,
    "Authorization": f"Bearer {AGENT_SECRET}",
}


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA acknowledgement API test",
        sequence=1,
        created_at="2026-07-29T00:00:00Z",
        expires_at="2026-07-29T00:05:00Z",
    )


def create_client(
    tmp_path: Path,
) -> tuple[
    TestClient,
    ExecutionMissionAcknowledgementStore,
    ExecutionMissionEvidencePersistence,
]:
    acknowledgement_store = (
        ExecutionMissionAcknowledgementStore()
    )

    persistence = ExecutionMissionEvidencePersistence(
        tmp_path
        / "execution_mission_evidence.json"
    )

    mission_registry = ExecutionMissionRegistry()

    mission_registry.register(
        ExecutionMissionRecord(
            mission=build_mission()
        )
    )

    intake = ExecutionMissionEvidenceIntake(
        persistence=persistence,
        acknowledgement_store=(
            acknowledgement_store
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
            BrokerExecutionEvidenceStore()
        ),
        mission_registry=mission_registry,
    )

    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    app = FastAPI()

    app.include_router(
        create_execution_mission_acknowledgement_router(
            intake,
            authenticator,
        )
    )

    return (
        TestClient(app),
        acknowledgement_store,
        persistence,
    )


def build_payload(
    agent_id: str = AGENT_ID,
) -> dict[str, object]:
    return {
        "mission_id": MISSION_ID,
        "agent_id": agent_id,
        "sequence": 1,
        "status": "ACCEPTED",
        "acknowledged_at": "2026-07-29T00:00:00Z",
    }


def test_acknowledge_mission_api(
    tmp_path: Path,
) -> None:
    client, store, persistence = create_client(
        tmp_path
    )

    response = client.post(
        "/missions/acknowledge",
        headers=AUTHENTICATION_HEADERS,
        json=build_payload(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "acknowledged",
        "mission_id": MISSION_ID,
        "store_size": 1,
    }

    assert persistence.size() == 1
    assert store.size() == 1


def test_acknowledge_mission_api_rejects_missing_credentials(
    tmp_path: Path,
) -> None:
    client, store, persistence = create_client(
        tmp_path
    )

    response = client.post(
        "/missions/acknowledge",
        json=build_payload(),
    )

    assert response.status_code == 401
    assert persistence.size() == 0
    assert store.size() == 0


def test_acknowledge_mission_api_rejects_wrong_agent_identity(
    tmp_path: Path,
) -> None:
    client, store, persistence = create_client(
        tmp_path
    )

    response = client.post(
        "/missions/acknowledge",
        headers=AUTHENTICATION_HEADERS,
        json=build_payload(
            agent_id="trusted-agent-999"
        ),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Acknowledgement evidence does not belong "
            "to authenticated Agent."
        ),
    }

    assert persistence.size() == 0
    assert store.size() == 0
def test_acknowledge_mission_api_rejects_mission_owned_by_other_agent(
    tmp_path: Path,
) -> None:
    acknowledgement_store = (
        ExecutionMissionAcknowledgementStore()
    )

    persistence = ExecutionMissionEvidencePersistence(
        tmp_path
        / "execution_mission_evidence.json"
    )

    mission_registry = ExecutionMissionRegistry()

    other_agent_mission = ExecutionMission(
        mission_id=MISSION_ID,
        agent_id="trusted-agent-999",
        account_fingerprint="other-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA cross-agent ownership test",
        sequence=1,
        created_at="2026-07-29T00:00:00Z",
        expires_at="2026-07-29T00:05:00Z",
    )

    mission_registry.register(
        ExecutionMissionRecord(
            mission=other_agent_mission
        )
    )

    intake = ExecutionMissionEvidenceIntake(
        persistence=persistence,
        acknowledgement_store=(
            acknowledgement_store
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
            BrokerExecutionEvidenceStore()
        ),
        mission_registry=mission_registry,
    )

    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    app = FastAPI()

    app.include_router(
        create_execution_mission_acknowledgement_router(
            intake,
            authenticator,
        )
    )

    client = TestClient(
        app,
        raise_server_exceptions=False,
    )

    response = client.post(
        "/missions/acknowledge",
        headers=AUTHENTICATION_HEADERS,
        json=build_payload(),
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "Execution mission evidence does not belong "
            "to mission Agent."
        ),
    }

    assert persistence.size() == 0
    assert acknowledgement_store.size() == 0