from dataclasses import FrozenInstanceError

import pytest

from backend.trading.control.control_mission_delivery_lease import (
    ControlMissionDeliveryLease,
)


def build_lease() -> ControlMissionDeliveryLease:
    return ControlMissionDeliveryLease(
        mission_id="control-001",
        agent_id="trusted-agent-001",
        leased_at="2026-08-15T00:00:00Z",
        expires_at="2026-08-15T00:00:30Z",
    )


def test_control_mission_delivery_lease_preserves_contract() -> None:
    lease = build_lease()

    assert lease.mission_id == "control-001"
    assert lease.agent_id == "trusted-agent-001"
    assert lease.leased_at == "2026-08-15T00:00:00Z"
    assert lease.expires_at == "2026-08-15T00:00:30Z"


def test_control_mission_delivery_lease_is_immutable() -> None:
    lease = build_lease()

    with pytest.raises(
        FrozenInstanceError
    ):
        lease.agent_id = "trusted-agent-002"