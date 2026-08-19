from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(
    0,
    str(
        ROOT_DIR
    ),
)

from fastapi.testclient import TestClient

from backend import main
from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "test-trusted-agent-secret"
MISSION_ID = "main-completed-001"

AUTHENTICATION_HEADERS = {
    "X-TODOBA-Agent-ID": AGENT_ID,
    "Authorization": f"Bearer {AGENT_SECRET}",
}


def test_main_app_contains_completed_api(
    isolated_main_execution_mission_evidence: Path,
) -> None:
    main.execution_mission_registry.register(
        ExecutionMissionRecord(
            mission=ExecutionMission(
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
                comment="TODOBA main completed API",
                sequence=1,
                created_at="2026-07-31T01:00:00Z",
                expires_at="2026-07-31T01:25:00Z",
            )
        )
    )

    client = TestClient(
        main.app
    )

    response = client.post(
        "/missions/completed",
        headers=AUTHENTICATION_HEADERS,
        json={
            "mission_id": MISSION_ID,
            "agent_id": AGENT_ID,
            "sequence": 1,
            "completed_at": "2026-07-31T01:20:00Z",
        },
    )

    assert response.status_code == 200

    assert (
        isolated_main_execution_mission_evidence.exists()
    )