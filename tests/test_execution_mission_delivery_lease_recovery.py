from pathlib import Path

from backend.trading.execution.execution_mission_delivery_lease import (
    ExecutionMissionDeliveryLease,
)
from backend.trading.execution.execution_mission_delivery_lease_persistence import (
    ExecutionMissionDeliveryLeasePersistence,
)
from backend.trading.execution.execution_mission_delivery_lease_recovery import (
    ExecutionMissionDeliveryLeaseRecovery,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)


def test_recovery_restores_persisted_delivery_leases(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "execution_mission_delivery_leases.json"
    )

    persistence = (
        ExecutionMissionDeliveryLeasePersistence(
            storage_path
        )
    )

    original_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    original_registry.acquire(
        ExecutionMissionDeliveryLease(
            mission_id="mission-001",
            agent_id="agent-001",
            leased_at="2026-08-08T00:00:00Z",
            expires_at="2026-08-08T00:00:30Z",
        )
    )

    persistence.save(
        original_registry
    )

    restored_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    recovery = (
        ExecutionMissionDeliveryLeaseRecovery(
            persistence=persistence,
            registry=restored_registry,
        )
    )

    restored_count = recovery.restore()

    assert restored_count == 1
    assert restored_registry.size() == 1

    restored_lease = restored_registry.get(
        "mission-001"
    )

    assert restored_lease is not None
    assert restored_lease.mission_id == (
        "mission-001"
    )
    assert restored_lease.agent_id == (
        "agent-001"
    )
    assert restored_lease.leased_at == (
        "2026-08-08T00:00:00Z"
    )
    assert restored_lease.expires_at == (
        "2026-08-08T00:00:30Z"
    )


def test_recovery_without_persisted_leases_returns_zero(
    tmp_path: Path,
) -> None:
    persistence = (
        ExecutionMissionDeliveryLeasePersistence(
            tmp_path
            / "missing-delivery-leases.json"
        )
    )

    registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    recovery = (
        ExecutionMissionDeliveryLeaseRecovery(
            persistence=persistence,
            registry=registry,
        )
    )

    assert recovery.restore() == 0
    assert registry.size() == 0