from backend.trading.execution.execution_mission import (
    ExecutionMission,
)

from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)


def build_mission(
    mission_id: str,
    agent_id: str,
) -> ExecutionMission:

    return ExecutionMission(
        mission_id=mission_id,
        agent_id=agent_id,
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Agent Scope Test",
        created_at="2026-08-04T00:00:00Z",
        expires_at="2026-08-05T00:00:00Z",
        sequence=1,
    )


def test_store_returns_only_matching_agent_mission():

    store = ExecutionMissionStore()

    agent_a_mission = build_mission(
        "mission-agent-a",
        "trusted-agent-a",
    )

    agent_b_mission = build_mission(
        "mission-agent-b",
        "trusted-agent-b",
    )

    store.push(
        agent_a_mission
    )

    store.push(
        agent_b_mission
    )

    received = store.pop_for_agent(
        "trusted-agent-b"
    )

    assert received is agent_b_mission

    assert store.size() == 1


def test_store_returns_none_when_agent_has_no_mission():

    store = ExecutionMissionStore()

    store.push(
        build_mission(
            "mission-agent-a",
            "trusted-agent-a",
        )
    )

    received = store.pop_for_agent(
        "trusted-agent-b"
    )

    assert received is None

    assert store.size() == 1