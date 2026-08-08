from pathlib import Path

from backend.trading.execution.execution_mission_delivery_lease import (
    ExecutionMissionDeliveryLease,
)
from backend.trading.execution.execution_mission_delivery_lease_persistence import (
    ExecutionMissionDeliveryLeasePersistence,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)


def build_lease(
    mission_id: str,
    agent_id: str,
) -> ExecutionMissionDeliveryLease:
    return ExecutionMissionDeliveryLease(
        mission_id=mission_id,
        agent_id=agent_id,
        leased_at="2026-08-08T00:00:00Z",
        expires_at="2026-08-08T00:00:30Z",
    )


def test_persistence_saves_and_restores_delivery_leases(
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

    registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    registry.acquire(
        build_lease(
            "mission-001",
            "agent-001",
        )
    )

    registry.acquire(
        build_lease(
            "mission-002",
            "agent-002",
        )
    )

    persistence.save(
        registry
    )

    restored_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    restored_count = persistence.restore(
        restored_registry
    )

    assert restored_count == 2
    assert restored_registry.size() == 2

    first = restored_registry.get(
        "mission-001"
    )

    second = restored_registry.get(
        "mission-002"
    )

    assert first is not None
    assert second is not None

    assert first.agent_id == "agent-001"
    assert first.leased_at == (
        "2026-08-08T00:00:00Z"
    )
    assert first.expires_at == (
        "2026-08-08T00:00:30Z"
    )

    assert second.agent_id == "agent-002"


def test_restore_missing_storage_returns_zero(
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

    assert persistence.restore(
        registry
    ) == 0

    assert registry.size() == 0