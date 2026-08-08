from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_delivery_lease import (
    ExecutionMissionDeliveryLease,
)
from backend.trading.execution.execution_mission_delivery_lease_persistence import (
    ExecutionMissionDeliveryLeasePersistence,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)
from backend.trading.execution.execution_mission_delivery_redelivery_processor import (
    ExecutionMissionDeliveryRedeliveryProcessor,
)
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)


MISSION_ID = "proof074-redelivery-001"
AGENT_ID = "trusted-agent-001"


def fixed_clock() -> datetime:
    return datetime(
        2026,
        8,
        8,
        12,
        1,
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
        comment="TODOBA Proof074 Redelivery",
        created_at="2026-08-08T12:00:00Z",
        expires_at="2026-08-08T13:00:00Z",
        sequence=1,
    )


def build_lease(
    *,
    expires_at: str,
) -> ExecutionMissionDeliveryLease:
    return ExecutionMissionDeliveryLease(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        leased_at="2026-08-08T12:00:00Z",
        expires_at=expires_at,
    )


def build_processor(
    *,
    repository: ExecutionMissionRepository,
    store: ExecutionMissionStore,
    lease_registry: ExecutionMissionDeliveryLeaseRegistry,
    lease_persistence: ExecutionMissionDeliveryLeasePersistence,
) -> ExecutionMissionDeliveryRedeliveryProcessor:
    delivery_bridge = ExecutionMissionDeliveryBridge(
        store
    )

    return ExecutionMissionDeliveryRedeliveryProcessor(
        repository=repository,
        delivery_bridge=delivery_bridge,
        lease_registry=lease_registry,
        clock=fixed_clock,
        lease_persistence=lease_persistence,
    )


def test_expired_lease_redelivers_and_persists_release(
    tmp_path: Path,
) -> None:
    repository = ExecutionMissionRepository()

    mission = build_mission()

    repository.save(
        mission
    )

    store = ExecutionMissionStore()

    lease_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    lease_registry.acquire(
        build_lease(
            expires_at="2026-08-08T12:00:30Z",
        )
    )

    lease_persistence = (
        ExecutionMissionDeliveryLeasePersistence(
            tmp_path / "delivery_leases.json"
        )
    )

    lease_persistence.save(
        lease_registry
    )

    processor = build_processor(
        repository=repository,
        store=store,
        lease_registry=lease_registry,
        lease_persistence=lease_persistence,
    )

    result = processor.process_next()

    assert result == mission

    assert store.size() == 1

    assert store.pop_for_agent(
        AGENT_ID
    ) == mission

    assert lease_registry.get(
        MISSION_ID
    ) is None

    restored_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    assert lease_persistence.restore(
        restored_registry
    ) == 0

    assert restored_registry.size() == 0


def test_active_lease_is_not_redelivered_or_removed(
    tmp_path: Path,
) -> None:
    repository = ExecutionMissionRepository()

    mission = build_mission()

    repository.save(
        mission
    )

    store = ExecutionMissionStore()

    lease_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    lease = build_lease(
        expires_at="2026-08-08T12:01:30Z",
    )

    lease_registry.acquire(
        lease
    )

    lease_persistence = (
        ExecutionMissionDeliveryLeasePersistence(
            tmp_path / "delivery_leases.json"
        )
    )

    lease_persistence.save(
        lease_registry
    )

    processor = build_processor(
        repository=repository,
        store=store,
        lease_registry=lease_registry,
        lease_persistence=lease_persistence,
    )

    result = processor.process_next()

    assert result is None

    assert store.size() == 0

    assert lease_registry.get(
        MISSION_ID
    ) == lease

    restored_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    assert lease_persistence.restore(
        restored_registry
    ) == 1

    assert restored_registry.get(
        MISSION_ID
    ) == lease


def test_expired_lease_without_mission_keeps_persisted_lease(
    tmp_path: Path,
) -> None:
    repository = ExecutionMissionRepository()

    store = ExecutionMissionStore()

    lease_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    lease = build_lease(
        expires_at="2026-08-08T12:00:30Z",
    )

    lease_registry.acquire(
        lease
    )

    lease_persistence = (
        ExecutionMissionDeliveryLeasePersistence(
            tmp_path / "delivery_leases.json"
        )
    )

    lease_persistence.save(
        lease_registry
    )

    processor = build_processor(
        repository=repository,
        store=store,
        lease_registry=lease_registry,
        lease_persistence=lease_persistence,
    )

    with pytest.raises(
        ValueError,
        match="Execution mission not found for redelivery.",
    ):
        processor.process_next()

    assert store.size() == 0

    assert lease_registry.get(
        MISSION_ID
    ) == lease

    restored_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    assert lease_persistence.restore(
        restored_registry
    ) == 1

    assert restored_registry.get(
        MISSION_ID
    ) == lease