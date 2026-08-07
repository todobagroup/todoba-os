import pytest

from backend.trading.execution.execution_mission_delivery_lease import (
    ExecutionMissionDeliveryLease,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)


def build_lease(
    *,
    mission_id: str = "proof073-mission-001",
    agent_id: str = "trusted-agent-001",
) -> ExecutionMissionDeliveryLease:
    return ExecutionMissionDeliveryLease(
        mission_id=mission_id,
        agent_id=agent_id,
        leased_at="2026-08-07T00:00:00Z",
        expires_at="2026-08-07T00:00:30Z",
    )


def test_registry_acquires_new_lease() -> None:
    registry = ExecutionMissionDeliveryLeaseRegistry()

    lease = build_lease()

    result = registry.acquire(
        lease
    )

    assert result == lease

    assert registry.get(
        lease.mission_id
    ) == lease

    assert registry.size() == 1


def test_registry_returns_existing_lease_for_same_agent() -> None:
    registry = ExecutionMissionDeliveryLeaseRegistry()

    first = build_lease()

    second = ExecutionMissionDeliveryLease(
        mission_id=first.mission_id,
        agent_id=first.agent_id,
        leased_at="2026-08-07T00:00:10Z",
        expires_at="2026-08-07T00:00:40Z",
    )

    registry.acquire(
        first
    )

    result = registry.acquire(
        second
    )

    assert result == first

    assert registry.size() == 1


def test_registry_rejects_conflicting_agent() -> None:
    registry = ExecutionMissionDeliveryLeaseRegistry()

    registry.acquire(
        build_lease(
            agent_id="trusted-agent-001",
        )
    )

    conflicting = build_lease(
        agent_id="trusted-agent-002",
    )

    with pytest.raises(
        ValueError
    ):
        registry.acquire(
            conflicting
        )

    assert registry.size() == 1


def test_registry_lists_active_leases() -> None:
    registry = ExecutionMissionDeliveryLeaseRegistry()

    first = build_lease(
        mission_id="proof073-mission-001",
    )

    second = build_lease(
        mission_id="proof073-mission-002",
    )

    registry.acquire(
        first
    )

    registry.acquire(
        second
    )

    assert registry.list() == [
        first,
        second,
    ]


def test_registry_releases_lease() -> None:
    registry = ExecutionMissionDeliveryLeaseRegistry()

    lease = build_lease()

    registry.acquire(
        lease
    )

    released = registry.release(
        lease.mission_id
    )

    assert released == lease

    assert registry.get(
        lease.mission_id
    ) is None

    assert registry.size() == 0


def test_registry_release_missing_returns_none() -> None:
    registry = ExecutionMissionDeliveryLeaseRegistry()

    result = registry.release(
        "missing-mission"
    )

    assert result is None

    assert registry.size() == 0