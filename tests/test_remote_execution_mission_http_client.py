"""
TODOBA Remote Execution Mission HTTP Client Tests

Proof:

ExecutionMission
->
Authenticated HTTP POST /missions/inject
->
TODOBA Cloud
"""

import sys
from pathlib import Path

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.remote_execution_mission_http_client import (
    RemoteExecutionMissionHttpClient,
)


def test_execution_mission_is_posted_to_cloud_with_executor_auth():
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "persisted",
                "mission_id": "proof090-001",
            }

    def fake_post(
        url,
        *,
        json,
        headers,
        timeout,
    ):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout

        return FakeResponse()

    original_post = httpx.post
    httpx.post = fake_post

    try:
        client = RemoteExecutionMissionHttpClient(
            cloud_base_url="https://api.todobagroup.com",
            executor_id="telegram-executor-001",
            executor_secret="proof090-secret",
            timeout_seconds=5.0,
        )

        mission = ExecutionMission(
            mission_id="proof090-001",
            agent_id="trusted-agent-001",
            account_fingerprint="demo-account",
            symbol="XAUUSD",
            order_type="SELL NOW",
            volume=0.01,
            entry=None,
            sl=4334.0,
            tp=4303.0,
            magic_number=10001,
            comment="TODOBA proof090",
            created_at="2026-08-10T00:00:00Z",
            expires_at="2026-08-10T00:02:00Z",
            sequence=90,
        )

        result = client.send(
            mission
        )

    finally:
        httpx.post = original_post

    assert captured["url"] == (
        "https://api.todobagroup.com/missions/inject"
    )

    assert captured["headers"] == {
        "X-TODOBA-Executor-ID": (
            "telegram-executor-001"
        ),
        "Authorization": (
            "Bearer proof090-secret"
        ),
    }

    assert captured["timeout"] == 5.0

    assert captured["json"]["mission_id"] == (
        "proof090-001"
    )
    assert captured["json"]["agent_id"] == (
        "trusted-agent-001"
    )
    assert captured["json"]["symbol"] == "XAUUSD"
    assert captured["json"]["order_type"] == "SELL NOW"
    assert captured["json"]["volume"] == 0.01
    assert captured["json"]["sl"] == 4334.0
    assert captured["json"]["tp"] == 4303.0
    assert captured["json"]["sequence"] == 90

    assert result == {
        "status": "persisted",
        "mission_id": "proof090-001",
    }