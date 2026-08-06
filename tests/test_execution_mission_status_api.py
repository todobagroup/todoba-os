from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)
from backend.trading.execution.execution_mission_status_api import (
    create_execution_mission_status_router,
)


def build_record() -> ExecutionMissionRecord:
    mission = ExecutionMission(
        mission_id="status-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Status Query",
        created_at="2026-08-06T00:00:00Z",
        expires_at="2026-08-06T01:00:00Z",
        sequence=1,
    )

    return ExecutionMissionRecord(
        mission=mission,
        status=ExecutionMissionStatus.ACKNOWLEDGED,
        delivered_at="2026-08-06T00:01:00Z",
        acknowledged_at="2026-08-06T00:02:00Z",
    )


def build_client(
    registry: ExecutionMissionRegistry,
) -> TestClient:
    app = FastAPI()

    app.include_router(
        create_execution_mission_status_router(
            registry
        )
    )

    return TestClient(
        app
    )


def test_status_api_returns_mission_record() -> None:
    registry = ExecutionMissionRegistry()

    registry.register(
        build_record()
    )

    client = build_client(
        registry
    )

    response = client.get(
        "/missions/status-001/status"
    )

    assert response.status_code == 200
    assert response.json() == {
        "mission_id": "status-001",
        "agent_id": "trusted-agent-001",
        "status": "ACKNOWLEDGED",
        "delivered_at": "2026-08-06T00:01:00Z",
        "acknowledged_at": "2026-08-06T00:02:00Z",
        "started_at": None,
        "completed_at": None,
        "failed_at": None,
        "failure_reason": None,
    }


def test_status_api_returns_not_found() -> None:
    registry = ExecutionMissionRegistry()

    client = build_client(
        registry
    )

    response = client.get(
        "/missions/missing/status"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Execution mission record not found.",
    }