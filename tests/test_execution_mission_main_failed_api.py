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


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "test-trusted-agent-secret"

AUTHENTICATION_HEADERS = {
    "X-TODOBA-Agent-ID": AGENT_ID,
    "Authorization": f"Bearer {AGENT_SECRET}",
}


def test_main_app_contains_failed_api(
    isolated_main_execution_mission_evidence: Path,
) -> None:
    client = TestClient(
        main.app
    )

    response = client.post(
        "/missions/failed",
        headers=AUTHENTICATION_HEADERS,
        json={
            "mission_id": "main-failed-001",
            "agent_id": AGENT_ID,
            "sequence": 1,
            "failed_at": "2026-07-31T01:30:00Z",
            "failure_reason": "broker_rejected_order",
        },
    )

    assert response.status_code == 200

    assert (
        isolated_main_execution_mission_evidence.exists()
    )