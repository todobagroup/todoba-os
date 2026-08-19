from pathlib import Path
import sys

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
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


MISSION_ID = "completed-001"
AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "test-trusted-agent-secret"

AUTHENTICATION_HEADERS = {
    "X-TODOBA-Agent-ID": AGENT_ID,
    "Authorization": f"Bearer {AGENT_SECRET}",
}


def build_mission(
    agent_id: str = AGENT_ID,
) -> ExecutionMission:
    return ExecutionMission(
        mission_id=MISSION_ID,
        agent_id=agent_id,
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA completed API test",
        sequence=1,
        created_at="2026-07-31T00:00:00Z",
        expires_at="2026-07-31T00:30:00Z",
    )


def build_client(
    tmp_path: Path,
    *,
    mission_agent_id: str = AGENT_ID,
    raise_server_exceptions: bool = True,
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

    mission_registry = ExecutionMissionRegistry()

    mission_registry.register(
        ExecutionMissionRecord(
           mission=build_mission(
               agent_id=mission_agent_id
)
        )
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
        mission_registry=mission_registry,
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
        TestClient(
    app,
    raise_server_exceptions=raise_server_exceptions,
),
        completed_store,
        persistence,
    )


def build_payload(
    agent_id: str = AGENT_ID,
) -> dict[str, object]:
    return {
        "mission_id": MISSION_ID,
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
        "mission_id": MISSION_ID,
        "store_size": 1,
    }

    assert persistence.size() == 1
    assert store.size() == 1

    evidence = store.pop()

    assert evidence is not None
    assert evidence.mission_id == MISSION_ID


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
def test_execution_mission_completed_api_rejects_mission_owned_by_other_agent(
    tmp_path: Path,
) -> None:
    client, store, persistence = build_client(
        tmp_path,
        mission_agent_id="trusted-agent-999",
        raise_server_exceptions=False,
    )

    response = client.post(
        "/missions/completed",
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
    assert store.size() == 0
