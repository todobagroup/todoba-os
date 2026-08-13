"""
TODOBA Execution Mission Persistent Injection Tests

Proof:

Authenticated Executor
->
Execution Mission Injection API
->
ExecutionMissionService
->
Persistent Repository Storage
"""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_injection_api import (
    create_execution_mission_injection_router,
)
from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)
from backend.trading.execution.execution_mission_service import (
    ExecutionMissionService,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)
from backend.trading.execution.executor_authenticator import (
    ExecutorAuthenticator,
)


def test_persistent_mission_injection_saves_repository(
    tmp_path,
):
    repository = ExecutionMissionRepository()

    persistence = ExecutionMissionPersistence(
        tmp_path / "execution_missions.json"
    )

    store = ExecutionMissionStore()

    bridge = ExecutionMissionDeliveryBridge(
        store
    )

    registry = ExecutionMissionRegistry()

    service = ExecutionMissionService(
        repository,
        persistence,
        bridge,
        registry,
    )

    authenticator = ExecutorAuthenticator(
        executor_id="telegram-executor-001",
        executor_secret="test-secret",
    )

    app = FastAPI()

    app.include_router(
        create_execution_mission_injection_router(
            service,
            authenticator,
        )
    )

    client = TestClient(app)

    response = client.post(
        "/missions/inject",
        headers={
            "X-TODOBA-Executor-ID": (
                "telegram-executor-001"
            ),
            "Authorization": (
                "Bearer test-secret"
            ),
        },
        json={
            "mission_id": "persistent-001",
            "agent_id": "trusted-agent-001",
            "account_fingerprint": "demo-account",
            "symbol": "XAUUSD",
            "order_type": "BUY LIMIT",
            "volume": 0.01,
            "entry": 4100.0,
            "sl": 4000.0,
            "tp": 4200.0,
            "magic_number": 10001,
            "comment": "TODOBA Persistent Proof",
            "created_at": "2026-07-29T00:00:00Z",
            "expires_at": "2026-07-30T00:00:00Z",
            "sequence": 1,
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "persisted",
        "mission_id": "persistent-001",
    }

    assert repository.size() == 1
    assert registry.size() == 1

    restored_repository = (
        ExecutionMissionRepository()
    )

    restored_count = persistence.restore(
        restored_repository
    )

    assert restored_count == 1

    mission = restored_repository.get(
        "persistent-001"
    )

    assert mission is not None
    assert mission.symbol == "XAUUSD"
    assert mission.order_type == "BUY LIMIT"