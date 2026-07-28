from dataclasses import FrozenInstanceError

import pytest

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id="mission-001",
        agent_id="agent-demo-001",
        account_fingerprint="demo-account-001",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4120.0,
        magic_number=10001,
        comment="TODOBA",
        created_at="2026-07-28T00:00:00Z",
        expires_at="2026-07-28T00:01:00Z",
        sequence=1,
    )


def test_execution_mission_preserves_contract():
    mission = build_mission()

    assert mission.mission_id == "mission-001"
    assert mission.agent_id == "agent-demo-001"
    assert mission.account_fingerprint == "demo-account-001"

    assert mission.symbol == "XAUUSD"
    assert mission.order_type == "BUY"
    assert mission.volume == 0.01
    assert mission.entry is None

    assert mission.sl == 4100.0
    assert mission.tp == 4120.0

    assert mission.magic_number == 10001
    assert mission.comment == "TODOBA"

    assert mission.created_at == "2026-07-28T00:00:00Z"
    assert mission.expires_at == "2026-07-28T00:01:00Z"
    assert mission.sequence == 1


def test_execution_mission_is_immutable():
    mission = build_mission()

    with pytest.raises(FrozenInstanceError):
        mission.sequence = 2