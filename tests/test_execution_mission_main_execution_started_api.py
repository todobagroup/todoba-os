from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from fastapi.testclient import TestClient

from backend.main import app


def test_main_app_contains_execution_started_api():

    client = TestClient(
        app
    )

    response = client.post(
        "/missions/execution_started",
        json={
            "mission_id": "main-started-001",
            "agent_id": "trusted-agent-001",
            "sequence": 1,
            "started_at": "2026-07-31T01:00:00Z",
        },
    )

    assert response.status_code == 200