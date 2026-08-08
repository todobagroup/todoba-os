from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest

from backend.trading.execution.execution_mission_delivery_lease_persistence import (
    ExecutionMissionDeliveryLeasePersistence,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)
from backend.trading.execution.execution_mission_delivery_lease_service import (
    ExecutionMissionDeliveryLeaseService,
)


def fixed_clock() -> datetime:
    return datetime(
        2026,
        8,
        8,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )


class FailingLeasePersistence(
    ExecutionMissionDeliveryLeasePersistence
):
    def save(
        self,
        registry: ExecutionMissionDeliveryLeaseRegistry,
    ) -> None:
        raise RuntimeError(
            "Lease persistence failed."
        )


def test_service_creates_lease_with_expiration() -> None:
    registry = ExecutionMissionDeliveryLeaseRegistry()

    service = ExecutionMissionDeliveryLeaseService(
        registry=registry,
        lease_seconds=30,
        clock=fixed_clock,
    )

    lease = service.acquire(
        mission_id="proof074-mission-001",
        agent_id="trusted-agent-001",
    )

    assert lease.mission_id == (
        "proof074-mission-001"
    )

    assert lease.agent_id == (
        "trusted-agent-001"
    )

    assert lease.leased_at == (
        "2026-08-08T12:00:00Z"
    )

    assert lease.expires_at == (
        "2026-08-08T12:00:30Z"
    )

    assert registry.size() == 1


def test_service_returns_existing_lease_for_same_agent() -> None:
    registry = ExecutionMissionDeliveryLeaseRegistry()

    service = ExecutionMissionDeliveryLeaseService(
        registry=registry,
        lease_seconds=30,
        clock=fixed_clock,
    )

    first = service.acquire(
        mission_id="proof074-mission-001",
        agent_id="trusted-agent-001",
    )

    second = service.acquire(
        mission_id="proof074-mission-001",
        agent_id="trusted-agent-001",
    )

    assert second == first
    assert registry.size() == 1


def test_service_rejects_conflicting_agent() -> None:
    registry = ExecutionMissionDeliveryLeaseRegistry()

    service = ExecutionMissionDeliveryLeaseService(
        registry=registry,
        lease_seconds=30,
        clock=fixed_clock,
    )

    service.acquire(
        mission_id="proof074-mission-001",
        agent_id="trusted-agent-001",
    )

    with pytest.raises(
        ValueError
    ):
        service.acquire(
            mission_id="proof074-mission-001",
            agent_id="trusted-agent-002",
        )

    assert registry.size() == 1


def test_service_rejects_non_positive_lease_seconds() -> None:
    registry = ExecutionMissionDeliveryLeaseRegistry()

    with pytest.raises(
        ValueError,
        match="lease_seconds must be greater than zero.",
    ):
        ExecutionMissionDeliveryLeaseService(
            registry=registry,
            lease_seconds=0,
            clock=fixed_clock,
        )


def test_service_rejects_naive_clock() -> None:
    registry = ExecutionMissionDeliveryLeaseRegistry()

    def naive_clock() -> datetime:
        return datetime(
            2026,
            8,
            8,
            12,
            0,
            0,
        )

    service = ExecutionMissionDeliveryLeaseService(
        registry=registry,
        lease_seconds=30,
        clock=naive_clock,
    )

    with pytest.raises(
        ValueError,
        match=(
            "clock must return timezone-aware datetime."
        ),
    ):
        service.acquire(
            mission_id="proof074-mission-001",
            agent_id="trusted-agent-001",
        )


def test_service_persists_acquired_lease(
    tmp_path: Path,
) -> None:
    registry = ExecutionMissionDeliveryLeaseRegistry()

    persistence = (
        ExecutionMissionDeliveryLeasePersistence(
            tmp_path / "delivery_leases.json"
        )
    )

    service = ExecutionMissionDeliveryLeaseService(
        registry=registry,
        lease_seconds=30,
        clock=fixed_clock,
        persistence=persistence,
    )

    service.acquire(
        mission_id="proof074-mission-001",
        agent_id="trusted-agent-001",
    )

    assert registry.size() == 1
    assert persistence.storage_path.exists()

    restored_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    assert persistence.restore(
        restored_registry
    ) == 1

    assert restored_registry.get(
        "proof074-mission-001"
    ) is not None


def test_service_rolls_back_new_lease_when_persistence_fails(
    tmp_path: Path,
) -> None:
    registry = ExecutionMissionDeliveryLeaseRegistry()

    persistence = FailingLeasePersistence(
        tmp_path / "delivery_leases.json"
    )

    service = ExecutionMissionDeliveryLeaseService(
        registry=registry,
        lease_seconds=30,
        clock=fixed_clock,
        persistence=persistence,
    )

    with pytest.raises(
        RuntimeError,
        match="Lease persistence failed.",
    ):
        service.acquire(
            mission_id="proof074-mission-001",
            agent_id="trusted-agent-001",
        )

    assert registry.size() == 0

    assert registry.get(
        "proof074-mission-001"
    ) is None