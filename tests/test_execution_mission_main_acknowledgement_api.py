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


def test_main_app_contains_acknowledgement_api() -> None:
    client = TestClient(
        app
    )

    response = client.post(
        "/missions/acknowledge",
        headers=AUTHENTICATION_HEADERS,
        json={
            "mission_id": "main-acknowledgement-001",
            "agent_id": AGENT_ID,
            "sequence": 1,
            "status": "ACCEPTED",
            "acknowledged_at": "2026-08-06T00:00:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "acknowledged"