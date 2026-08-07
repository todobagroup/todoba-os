from dataclasses import FrozenInstanceError

import pytest

from backend.trading.execution.execution_mission_delivery_lease import (
    ExecutionMissionDeliveryLease,
)


def test_delivery_lease_preserves_identity() -> None:
    lease = ExecutionMissionDeliveryLease(
        mission_id="proof073-mission-001",
        agent_id="trusted-agent-001",
        leased_at="2026-08-07T00:00:00Z",
        expires_at="2026-08-07T00:00:30Z",
    )

    assert lease.mission_id == (
        "proof073-mission-001"
    )

    assert lease.agent_id == (
        "trusted-agent-001"
    )

    assert lease.leased_at == (
        "2026-08-07T00:00:00Z"
    )

    assert lease.expires_at == (
        "2026-08-07T00:00:30Z"
    )


def test_delivery_lease_is_immutable() -> None:
    lease = ExecutionMissionDeliveryLease(
        mission_id="proof073-mission-002",
        agent_id="trusted-agent-001",
        leased_at="2026-08-07T00:00:00Z",
        expires_at="2026-08-07T00:00:30Z",
    )

    with pytest.raises(
        FrozenInstanceError
    ):
        lease.agent_id = "trusted-agent-002"