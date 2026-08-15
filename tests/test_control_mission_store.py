from dataclasses import replace

import pytest

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_store import (
    ControlMissionStore,
)


def build_mission(
    *,
    mission_id: str = "control-001",
    agent_id: str = "agent-demo-001",
    sequence: int = 1,
) -> ControlMission:
    return ControlMission(
        mission_id=mission_id,
        agent_id=agent_id,
        account_fingerprint="demo-account-001",
        action=ControlAction.CLOSE_GREEN,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=5414928751,
        created_at="2026-08-15T00:00:00Z",
        expires_at="2026-08-15T00:01:00Z",
        sequence=sequence,
    )


def test_store_pushes_and_pops_fifo() -> None:
    store = ControlMissionStore()

    first = build_mission()
    second = build_mission(
        mission_id="control-002",
        sequence=2,
    )

    store.push(first)
    store.push(second)

    assert store.size() == 2
    assert store.pop() == first
    assert store.pop() == second
    assert store.pop() is None


def test_store_routes_mission_to_requested_agent() -> None:
    store = ControlMissionStore()

    agent_one = build_mission()
    agent_two = build_mission(
        mission_id="control-002",
        agent_id="agent-demo-002",
        sequence=2,
    )

    store.push(agent_one)
    store.push(agent_two)

    assert store.pop_for_agent(
        "agent-demo-002"
    ) == agent_two

    assert store.pop_for_agent(
        "missing-agent"
    ) is None

    assert store.pop() == agent_one


def test_same_mission_retry_is_idempotent() -> None:
    store = ControlMissionStore()
    mission = build_mission()

    first = store.push(
        mission
    )
    second = store.push(
        mission
    )

    assert first is mission
    assert second is mission
    assert store.size() == 1


def test_same_id_with_different_payload_is_rejected() -> None:
    store = ControlMissionStore()
    mission = build_mission()

    store.push(
        mission
    )

    tampered = replace(
        mission,
        action=ControlAction.CLOSE_RED,
    )

    with pytest.raises(
        ValueError,
        match="different payload",
    ):
        store.push(
            tampered
        )


def test_store_remembers_mission_after_delivery() -> None:
    store = ControlMissionStore()
    mission = build_mission()

    store.push(
        mission
    )

    assert store.pop() == mission
    assert store.get(
        mission.mission_id
    ) == mission


def test_store_rejects_wrong_contract() -> None:
    store = ControlMissionStore()

    with pytest.raises(
        TypeError,
        match="push requires ControlMission",
    ):
        store.push(
            "not-a-control-mission"
        )


def test_redeliver_requeues_mission_after_pop() -> None:
    store = ControlMissionStore()
    mission = build_mission()
    store.push(
        mission
    )
    assert store.pop() == mission
    assert store.size() == 0

    redelivered = store.redeliver(
        mission
    )

    assert redelivered == mission
    assert store.size() == 1
    assert store.pop_for_agent(
        "agent-demo-001"
    ) == mission


def test_redeliver_does_not_duplicate_queued_mission() -> None:
    store = ControlMissionStore()
    mission = build_mission()
    store.push(
        mission
    )

    first = store.redeliver(
        mission
    )
    second = store.redeliver(
        mission
    )

    assert first == mission
    assert second == mission
    assert store.size() == 1


def test_redeliver_registers_unknown_mission() -> None:
    store = ControlMissionStore()
    mission = build_mission()

    result = store.redeliver(
        mission
    )

    assert result == mission
    assert store.get(
        mission.mission_id
    ) == mission
    assert store.size() == 1


def test_redeliver_rejects_conflicting_payload() -> None:
    store = ControlMissionStore()
    mission = build_mission()
    store.push(
        mission
    )
    store.pop()
    tampered = replace(
        mission,
        action=ControlAction.CLOSE_RED,
    )

    with pytest.raises(
        ValueError,
        match="different payload",
    ):
        store.redeliver(
            tampered
        )


def test_redeliver_rejects_wrong_contract() -> None:
    store = ControlMissionStore()

    with pytest.raises(
        TypeError,
        match="redeliver requires ControlMission",
    ):
        store.redeliver(
            "not-a-control-mission"
        )