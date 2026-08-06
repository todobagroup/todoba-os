from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient

from backend.main import app


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "test-trusted-agent-secret"

AUTHENTICATION_HEADERS = {
    "X-TODOBA-Agent-ID": AGENT_ID,
    "Authorization": f"Bearer {AGENT_SECRET}",
}


def test_main_app_contains_execution_started_api() -> None:
    client = TestClient(
        app
    )

    response = client.post(
        "/missions/execution_started",
        headers=AUTHENTICATION_HEADERS,
        json={
            "mission_id": "main-started-001",
            "agent_id": AGENT_ID,
            "sequence": 1,
            "started_at": "2026-07-31T01:00:00Z",
        },
    )

    assert response.status_code == 200