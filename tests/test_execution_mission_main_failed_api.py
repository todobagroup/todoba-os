from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from fastapi.testclient import TestClient

from backend.main import app


def test_main_app_contains_failed_api():

    client = TestClient(
        app
    )

    response = client.post(
        "/missions/failed",
        json={
            "mission_id": "main-failed-001",
            "agent_id": "trusted-agent-001",
            "sequence": 1,
            "failed_at": "2026-07-31T01:30:00Z",
            "failure_reason": "broker_rejected_order",
        },
    )

    assert response.status_code == 200