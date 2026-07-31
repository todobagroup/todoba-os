from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from fastapi.testclient import TestClient

from backend.main import app


def test_main_app_contains_completed_api():

    client = TestClient(
        app
    )

    response = client.post(
        "/missions/completed",
        json={
            "mission_id": "main-completed-001",
            "agent_id": "trusted-agent-001",
            "sequence": 1,
            "completed_at": "2026-07-31T01:20:00Z",
        },
    )

    assert response.status_code == 200