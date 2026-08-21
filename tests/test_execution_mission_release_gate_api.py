"""
TODOBA Execution Mission Release Gate API Tests

CAP 3I Owner 2 proof:

The authenticated Trusted Agent polling boundary must
check ExecutionMissionReleaseGuard before removing a
mission from the delivery queue.

Required rules:

- not READY:
  return empty
  keep mission queued
  create no delivery lease
  preserve CREATED lifecycle state

- READY:
  release the mission
  remove it from the queue
  acquire delivery lease
  advance lifecycle to DELIVERED
"""

from datetime import UTC
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading.execution.broker_state import (
    BrokerState,
)
from backend.trading.execution.broker_state_store import (
    BrokerStateStore,
)
from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_api import (
    create_execution_mission_router,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)
from backend.trading.execution.execution_mission_delivery_lease_service import (
    ExecutionMissionDeliveryLeaseService,
)
from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_release_guard import (
    ExecutionMissionReleaseGuard,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)
from backend.trading.execution.trusted_agent_account_binding_guard import (
    TrustedAgentAccountBindingGuard,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


AGENT_ID = "trusted-agent-001"
AGENT_SECRET = "release-gate-test-secret"
ACCOUNT_FINGERPRINT = "broker-a:100001"

NOW = datetime(
    2026,
    8,
    21,
    8,
    0,
    10,
    tzinfo=UTC,
)

BROKER_STATE_RECEIVED_AT = datetime(
    2026,
    8,
    21,
    8,
    0,
    0,
    tzinfo=UTC,
)

AUTH_HEADERS = {
    "X-TODOBA-Agent-ID": AGENT_ID,
    "Authorization": (
        f"Bearer {AGENT_SECRET}"
    ),
}


def build_mission(
    *,
    account_fingerprint: str = ACCOUNT_FINGERPRINT,
) -> ExecutionMission:
    return ExecutionMission(
        mission_id="cap3i-release-gate-001",
        agent_id=AGENT_ID,
        account_fingerprint=account_fingerprint,
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4300.0,
        tp=4500.0,
        magic_number=10001,
        comment="TODOBA CAP 3I",
        created_at="2026-08-21T07:59:00Z",
        expires_at="2026-08-21T08:10:00Z",
        sequence=1,
    )


def build_broker_state() -> BrokerState:
    return BrokerState(
        account_fingerprint=ACCOUNT_FINGERPRINT,
        equity=10000.0,
        open_position_count=0,
        pending_order_count=0,
        symbol="XAUUSD",
        bid=4400.0,
        ask=4400.2,
        spread_points=20.0,
    )


def build_account_binding_guard(
    *,
    tmp_path: Path,
) -> TrustedAgentAccountBindingGuard:
    store = TrustedAgentAccountBindingStore(
        tmp_path
        / "trusted_agent_account_bindings.json"
    )

    store.initialize_empty()

    store.bind(
        agent_id=AGENT_ID,
        account_fingerprint=ACCOUNT_FINGERPRINT,
    )

    return TrustedAgentAccountBindingGuard(
        store
    )


def build_stack(
    *,
    tmp_path: Path,
    broker_state_ready: bool,
):
    mission = build_mission()

    mission_store = ExecutionMissionStore()

    mission_store.push(
        mission
    )

    mission_registry = ExecutionMissionRegistry()

    mission_registry.register(
        ExecutionMissionRecord(
            mission=mission
        )
    )

    lifecycle_service = (
        ExecutionMissionLifecycleService(
            mission_registry
        )
    )

    lease_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    lease_service = (
        ExecutionMissionDeliveryLeaseService(
            registry=lease_registry,
            lease_seconds=30.0,
            clock=lambda: NOW,
        )
    )

    broker_state_store = BrokerStateStore(
        clock=lambda: BROKER_STATE_RECEIVED_AT
    )

    if broker_state_ready:
        broker_state_store.save(
            build_broker_state(),
            agent_id=AGENT_ID,
        )

    release_guard = ExecutionMissionReleaseGuard(
        broker_state_store=broker_state_store,
        account_binding_guard=(
            build_account_binding_guard(
                tmp_path=tmp_path
            )
        ),
        max_age_seconds=30.0,
        clock=lambda: NOW,
    )

    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    app = FastAPI()

    app.include_router(
        create_execution_mission_router(
            mission_store,
            authenticator,
            lease_service,
            lifecycle_service,
            release_guard=release_guard,
        )
    )

    return (
        TestClient(app),
        mission,
        mission_store,
        mission_registry,
        lease_registry,
    )


def test_not_ready_agent_cannot_remove_mission_from_queue(
    tmp_path: Path,
) -> None:
    (
        client,
        mission,
        mission_store,
        mission_registry,
        lease_registry,
    ) = build_stack(
        tmp_path=tmp_path,
        broker_state_ready=False,
    )

    response = client.get(
        "/missions/next",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "empty",
        "mission": None,
    }

    assert mission_store.size() == 1

    assert mission_store.get(
        mission.mission_id
    ) == mission

    assert lease_registry.size() == 0

    record = mission_registry.get(
        mission.mission_id
    )

    assert record is not None

    assert record.status == (
        ExecutionMissionStatus.CREATED
    )


def test_ready_agent_releases_mission_and_acquires_lease(
    tmp_path: Path,
) -> None:
    (
        client,
        mission,
        mission_store,
        mission_registry,
        lease_registry,
    ) = build_stack(
        tmp_path=tmp_path,
        broker_state_ready=True,
    )

    response = client.get(
        "/missions/next",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "available"

    assert payload["mission"]["mission_id"] == (
        mission.mission_id
    )

    assert payload["agent_id"] == AGENT_ID

    assert mission_store.size() == 0

    lease = lease_registry.get(
        mission.mission_id
    )

    assert lease is not None
    assert lease.agent_id == AGENT_ID

    record = mission_registry.get(
        mission.mission_id
    )

    assert record is not None

    assert record.status == (
        ExecutionMissionStatus.DELIVERED
    )

def test_ready_agent_cannot_release_mission_for_wrong_account(
    tmp_path: Path,
) -> None:
    wrong_account = "broker-b:200002"

    mission = build_mission(
        account_fingerprint=wrong_account
    )

    mission_store = ExecutionMissionStore()

    mission_store.push(
        mission
    )

    mission_registry = ExecutionMissionRegistry()

    mission_registry.register(
        ExecutionMissionRecord(
            mission=mission
        )
    )

    lifecycle_service = (
        ExecutionMissionLifecycleService(
            mission_registry
        )
    )

    lease_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    lease_service = (
        ExecutionMissionDeliveryLeaseService(
            registry=lease_registry,
            lease_seconds=30.0,
            clock=lambda: NOW,
        )
    )

    broker_state_store = BrokerStateStore(
        clock=lambda: BROKER_STATE_RECEIVED_AT
    )

    broker_state_store.save(
        build_broker_state(),
        agent_id=AGENT_ID,
    )

    release_guard = ExecutionMissionReleaseGuard(
        broker_state_store=broker_state_store,
        account_binding_guard=(
            build_account_binding_guard(
                tmp_path=tmp_path
            )
        ),
        max_age_seconds=30.0,
        clock=lambda: NOW,
    )

    authenticator = TrustedAgentAuthenticator(
        agent_id=AGENT_ID,
        agent_secret=AGENT_SECRET,
    )

    app = FastAPI()

    app.include_router(
        create_execution_mission_router(
            mission_store,
            authenticator,
            lease_service,
            lifecycle_service,
            release_guard=release_guard,
        )
    )

    client = TestClient(app)

    response = client.get(
        "/missions/next",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "empty",
        "mission": None,
    }

    assert mission_store.size() == 1

    assert mission_store.get(
        mission.mission_id
    ) == mission

    assert lease_registry.size() == 0

    record = mission_registry.get(
        mission.mission_id
    )

    assert record is not None

    assert record.status == (
        ExecutionMissionStatus.CREATED
    )
