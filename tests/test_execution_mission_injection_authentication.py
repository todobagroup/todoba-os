"""
TODOBA Execution Mission Injection Authentication Tests

Proof:

Executor
->
POST /missions/inject
->
Executor Authentication
->
ExecutionMissionService

Unauthenticated requests must be rejected.
Authenticated requests may inject missions.
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


def create_test_client(
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
        executor_secret="proof091-secret",
    )

    app = FastAPI()

    app.include_router(
        create_execution_mission_injection_router(
            service,
            authenticator,
        )
    )

    return (
        TestClient(app),
        repository,
        registry,
        store,
    )


def mission_payload():
    return {
        "mission_id": "proof091-injection-001",
        "agent_id": "trusted-agent-001",
        "account_fingerprint": "demo-account",
        "symbol": "XAUUSD",
        "order_type": "SELL",
        "volume": 0.01,
        "entry": None,
        "sl": 4334.0,
        "tp": 4303.0,
        "magic_number": 10001,
        "comment": "TODOBA Proof091",
        "created_at": "2026-08-10T10:00:00Z",
        "expires_at": "2026-08-10T11:00:00Z",
        "sequence": 91,
    }


def test_injection_without_executor_credentials_returns_401(
    tmp_path,
):
    client, repository, registry, store = (
        create_test_client(
            tmp_path
        )
    )

    response = client.post(
        "/missions/inject",
        json=mission_payload(),
    )

    assert response.status_code == 401

    assert repository.size() == 0
    assert registry.size() == 0
    assert store.size() == 0


def test_injection_with_invalid_executor_secret_returns_401(
    tmp_path,
):
    client, repository, registry, store = (
        create_test_client(
            tmp_path
        )
    )

    response = client.post(
        "/missions/inject",
        headers={
            "X-TODOBA-Executor-ID": (
                "telegram-executor-001"
            ),
            "Authorization": (
                "Bearer wrong-secret"
            ),
        },
        json=mission_payload(),
    )

    assert response.status_code == 401

    assert repository.size() == 0
    assert registry.size() == 0
    assert store.size() == 0


def test_authenticated_executor_can_inject_mission(
    tmp_path,
):
    client, repository, registry, store = (
        create_test_client(
            tmp_path
        )
    )

    response = client.post(
        "/missions/inject",
        headers={
            "X-TODOBA-Executor-ID": (
                "telegram-executor-001"
            ),
            "Authorization": (
                "Bearer proof091-secret"
            ),
        },
        json=mission_payload(),
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "persisted",
        "mission_id": "proof091-injection-001",
    }

    assert repository.size() == 1
    assert registry.size() == 1
    assert store.size() == 1