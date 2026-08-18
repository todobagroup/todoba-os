from datetime import datetime
from datetime import timezone

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_delivery_lease import (
    ExecutionMissionDeliveryLease,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)
from backend.trading.execution.execution_mission_delivery_redelivery_processor import (
    ExecutionMissionDeliveryRedeliveryProcessor,
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
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)


MISSION_ID = "explicit-redelivery-001"
AGENT_ID = "trusted-agent-001"


def fixed_clock() -> datetime:
    return datetime(
        2026,
        8,
        18,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Explicit Redelivery",
        created_at="2026-08-18T11:00:00Z",
        expires_at="2026-08-18T13:00:00Z",
        sequence=1,
    )


def test_expired_delivery_explicitly_requeues_known_mission():
    mission = build_mission()

    repository = ExecutionMissionRepository()
    repository.save(
        mission
    )

    store = ExecutionMissionStore()
    bridge = ExecutionMissionDeliveryBridge(
        store
    )

    bridge.deliver(
        mission
    )

    delivered = store.pop_for_agent(
        AGENT_ID
    )

    assert delivered == mission
    assert store.size() == 0

    assert store.get(
        MISSION_ID
    ) == mission

    lease_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    lease_registry.acquire(
        ExecutionMissionDeliveryLease(
            mission_id=MISSION_ID,
            agent_id=AGENT_ID,
            leased_at="2026-08-18T11:58:00Z",
            expires_at="2026-08-18T11:59:00Z",
        )
    )

    mission_registry = ExecutionMissionRegistry()

    mission_registry.register(
        ExecutionMissionRecord(
            mission=mission,
            status=ExecutionMissionStatus.DELIVERED,
            delivered_at="2026-08-18T11:58:00Z",
            delivery_attempt_count=1,
        )
    )

    lifecycle_service = (
        ExecutionMissionLifecycleService(
            mission_registry
        )
    )

    processor = (
        ExecutionMissionDeliveryRedeliveryProcessor(
            repository=repository,
            delivery_bridge=bridge,
            lease_registry=lease_registry,
            clock=fixed_clock,
            lifecycle_service=lifecycle_service,
        )
    )

    result = processor.process_next()

    assert result == mission

    assert store.size() == 1

    assert store.pop_for_agent(
        AGENT_ID
    ) == mission