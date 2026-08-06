from fastapi.testclient import TestClient

from backend.main import (
    app,
    execution_mission_registry,
)
from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


def build_record() -> ExecutionMissionRecord:
    mission = ExecutionMission(
        mission_id="main-status-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Main Status Query",
        created_at="2026-08-06T00:00:00Z",
        expires_at="2026-08-06T01:00:00Z",
        sequence=1,
    )

    return ExecutionMissionRecord(
        mission=mission,
        status=ExecutionMissionStatus.ACKNOWLEDGED,
        acknowledged_at="2026-08-06T00:02:00Z",
    )


def test_main_app_contains_execution_mission_status_api() -> None:
    execution_mission_registry.register(
        build_record()
    )

    client = TestClient(
        app
    )

    response = client.get(
        "/missions/main-status-001/status"
    )

    assert response.status_code == 200

    assert response.json() == {
        "mission_id": "main-status-001",
        "agent_id": "trusted-agent-001",
        "status": "ACKNOWLEDGED",
        "delivered_at": None,
        "acknowledged_at": "2026-08-06T00:02:00Z",
        "started_at": None,
        "completed_at": None,
        "failed_at": None,
        "failure_reason": None,
    }