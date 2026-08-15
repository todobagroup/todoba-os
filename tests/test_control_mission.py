from dataclasses import FrozenInstanceError

import pytest

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)


def build_mission() -> ControlMission:
    return ControlMission(
        mission_id="control-001",
        agent_id="agent-demo-001",
        account_fingerprint="demo-account-001",
        action=ControlAction.CLOSE_GREEN,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=5414928751,
        created_at="2026-08-15T00:00:00Z",
        expires_at="2026-08-15T00:01:00Z",
        sequence=1,
    )


def test_control_mission_preserves_contract() -> None:
    mission = build_mission()

    assert mission.mission_id == "control-001"
    assert mission.agent_id == "agent-demo-001"
    assert mission.account_fingerprint == (
        "demo-account-001"
    )

    assert mission.action == ControlAction.CLOSE_GREEN
    assert mission.symbol == "XAUUSD"
    assert mission.magic_number == 10001

    assert mission.requested_by_sender_id == 5414928751

    assert mission.created_at == "2026-08-15T00:00:00Z"
    assert mission.expires_at == "2026-08-15T00:01:00Z"
    assert mission.sequence == 1


def test_control_mission_is_immutable() -> None:
    mission = build_mission()

    with pytest.raises(FrozenInstanceError):
        mission.sequence = 2


def test_control_mission_has_no_trade_entry_fields() -> None:
    mission = build_mission()

    assert not hasattr(mission, "order_type")
    assert not hasattr(mission, "volume")
    assert not hasattr(mission, "entry")
    assert not hasattr(mission, "sl")
    assert not hasattr(mission, "tp")