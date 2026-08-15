from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.control.control_mission_delivery_bridge import (
    ControlMissionDeliveryBridge,
)
from backend.trading.control.control_mission_injection_api import (
    create_control_mission_injection_router,
)
from backend.trading.control.control_mission_lifecycle_service import (
    ControlMissionLifecycleService,
)
from backend.trading.control.control_mission_persistence import (
    ControlMissionPersistence,
)
from backend.trading.control.control_mission_record_persistence import (
    ControlMissionRecordPersistence,
)
from backend.trading.control.control_mission_registry import (
    ControlMissionRegistry,
)
from backend.trading.control.control_mission_repository import (
    ControlMissionRepository,
)
from backend.trading.control.control_mission_service import (
    ControlMissionService,
)
from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
)
from backend.trading.control.control_mission_store import (
    ControlMissionStore,
)
from backend.trading.execution.executor_authenticator import (
    ExecutorAuthenticator,
)


EXECUTOR_ID = "telegram-executor-001"
EXECUTOR_SECRET = "proof178-executor-secret"
MISSION_ID = "control-api-001"


def build_client(
    tmp_path: Path,
) -> tuple[
    TestClient,
    ControlMissionRepository,
    ControlMissionRegistry,
    ControlMissionStore,
]:
    repository = ControlMissionRepository()
    persistence = ControlMissionPersistence(
        tmp_path / "control_missions.json"
    )
    registry = ControlMissionRegistry()
    record_persistence = ControlMissionRecordPersistence(
        tmp_path / "control_mission_records.json"
    )
    store = ControlMissionStore()
    bridge = ControlMissionDeliveryBridge(
        store
    )
    lifecycle_service = ControlMissionLifecycleService(
        registry,
        record_persistence,
        repository=repository,
        mission_persistence=persistence,
    )
    service = ControlMissionService(
        repository,
        persistence,
        bridge,
        registry,
        lifecycle_service,
    )
    authenticator = ExecutorAuthenticator(
        executor_id=EXECUTOR_ID,
        executor_secret=EXECUTOR_SECRET,
    )
    app = FastAPI()
    app.include_router(
        create_control_mission_injection_router(
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


def executor_headers(
    *,
    secret: str = EXECUTOR_SECRET,
) -> dict[str, str]:
    return {
        "X-TODOBA-Executor-ID": EXECUTOR_ID,
        "Authorization": f"Bearer {secret}",
    }


def mission_payload() -> dict:
    return {
        "mission_id": MISSION_ID,
        "agent_id": "trusted-agent-001",
        "account_fingerprint": "account-test",
        "action": "CLOSE_GREEN",
        "symbol": "XAUUSD",
        "magic_number": 10001,
        "requested_by_sender_id": 5414928751,
        "created_at": "2026-08-15T00:00:00Z",
        "expires_at": "2026-08-15T00:01:00Z",
        "sequence": 1,
    }


def test_authenticated_executor_can_inject_control_mission(
    tmp_path: Path,
) -> None:
    client, repository, registry, store = build_client(
        tmp_path
    )

    response = client.post(
        "/control/missions/inject",
        headers=executor_headers(),
        json=mission_payload(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "persisted",
        "mission_id": MISSION_ID,
    }
    assert repository.get(
        MISSION_ID
    ) is not None
    assert registry.get(
        MISSION_ID
    ).status == ControlMissionStatus.QUEUED
    assert store.size() == 1


def test_injection_retry_does_not_duplicate_control_mission(
    tmp_path: Path,
) -> None:
    client, repository, registry, store = build_client(
        tmp_path
    )

    first = client.post(
        "/control/missions/inject",
        headers=executor_headers(),
        json=mission_payload(),
    )
    second = client.post(
        "/control/missions/inject",
        headers=executor_headers(),
        json=mission_payload(),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert repository.size() == 1
    assert registry.size() == 1
    assert store.size() == 1


def test_injection_requires_executor_authentication(
    tmp_path: Path,
) -> None:
    client, _, _, _ = build_client(
        tmp_path
    )

    response = client.post(
        "/control/missions/inject",
        json=mission_payload(),
    )

    assert response.status_code == 401


def test_injection_rejects_wrong_executor_secret(
    tmp_path: Path,
) -> None:
    client, _, _, _ = build_client(
        tmp_path
    )

    response = client.post(
        "/control/missions/inject",
        headers=executor_headers(
            secret="wrong-secret"
        ),
        json=mission_payload(),
    )

    assert response.status_code == 401


def test_injection_rejects_unknown_control_action(
    tmp_path: Path,
) -> None:
    client, repository, registry, store = build_client(
        tmp_path
    )
    payload = mission_payload()
    payload["action"] = "CLOSE_ANYTHING"

    response = client.post(
        "/control/missions/inject",
        headers=executor_headers(),
        json=payload,
    )

    assert response.status_code == 422
    assert repository.size() == 0
    assert registry.size() == 0
    assert store.size() == 0