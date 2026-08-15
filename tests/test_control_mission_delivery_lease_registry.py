from dataclasses import replace

import pytest

from backend.trading.control.control_mission_delivery_lease import (
    ControlMissionDeliveryLease,
)
from backend.trading.control.control_mission_delivery_lease_registry import (
    ControlMissionDeliveryLeaseRegistry,
)


def build_lease(
    *,
    agent_id: str = "trusted-agent-001",
) -> ControlMissionDeliveryLease:
    return ControlMissionDeliveryLease(
        mission_id="control-001",
        agent_id=agent_id,
        leased_at="2026-08-15T00:00:00Z",
        expires_at="2026-08-15T00:00:30Z",
    )


def test_registry_acquires_and_reads_lease() -> None:
    registry = ControlMissionDeliveryLeaseRegistry()
    lease = build_lease()

    acquired = registry.acquire(
        lease
    )

    assert acquired == lease
    assert registry.get(
        "control-001"
    ) == lease
    assert registry.list() == [lease]
    assert registry.size() == 1


def test_same_agent_retry_returns_existing_lease() -> None:
    registry = ControlMissionDeliveryLeaseRegistry()
    first = build_lease()
    retry = replace(
        first,
        leased_at="2026-08-15T00:00:10Z",
        expires_at="2026-08-15T00:00:40Z",
    )

    registry.acquire(
        first
    )
    acquired = registry.acquire(
        retry
    )

    assert acquired == first
    assert registry.size() == 1


def test_different_agent_cannot_take_existing_lease() -> None:
    registry = ControlMissionDeliveryLeaseRegistry()
    registry.acquire(
        build_lease()
    )

    with pytest.raises(
        ValueError,
        match="already belongs to another Agent",
    ):
        registry.acquire(
            build_lease(
                agent_id="trusted-agent-002"
            )
        )


def test_registry_releases_existing_lease() -> None:
    registry = ControlMissionDeliveryLeaseRegistry()
    lease = build_lease()
    registry.acquire(
        lease
    )

    released = registry.release(
        "control-001"
    )

    assert released == lease
    assert registry.get(
        "control-001"
    ) is None
    assert registry.size() == 0


def test_registry_release_missing_returns_none() -> None:
    registry = ControlMissionDeliveryLeaseRegistry()

    assert registry.release(
        "missing-control"
    ) is None


def test_registry_rejects_invalid_lease() -> None:
    registry = ControlMissionDeliveryLeaseRegistry()

    with pytest.raises(
        TypeError,
        match="requires ControlMissionDeliveryLease",
    ):
        registry.acquire(
            "not-a-lease"
        )