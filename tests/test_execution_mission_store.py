from dataclasses import replace

import pytest

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)


def build_mission(
    mission_id: str = "mission-001",
) -> ExecutionMission:
    return ExecutionMission(
        mission_id=mission_id,
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


def test_store_pushes_and_pops_mission():
    store = ExecutionMissionStore()
    mission = build_mission()

    stored = store.push(
        mission
    )

    assert stored is mission
    assert store.size() == 1

    received = store.pop()

    assert received is mission
    assert store.size() == 0


def test_store_preserves_fifo_order():
    store = ExecutionMissionStore()

    first = build_mission(
        "mission-001"
    )
    second = build_mission(
        "mission-002"
    )

    store.push(first)
    store.push(second)

    assert store.pop() is first
    assert store.pop() is second


def test_store_returns_none_when_empty():
    store = ExecutionMissionStore()

    assert store.pop() is None
    assert store.size() == 0


def test_store_rejects_invalid_mission():
    store = ExecutionMissionStore()

    with pytest.raises(
        TypeError,
        match="push requires ExecutionMission",
    ):
        store.push(
            {"mission_id": "invalid"}
        )


def test_store_push_is_idempotent_for_identical_mission():
    store = ExecutionMissionStore()
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


def test_store_rejects_same_mission_id_with_different_payload():
    store = ExecutionMissionStore()
    mission = build_mission()

    store.push(
        mission
    )

    conflicting = replace(
        mission,
        sequence=2,
    )

    with pytest.raises(
        ValueError,
        match=(
            "mission_id already exists with "
            "different payload"
        ),
    ):
        store.push(
            conflicting
        )

    assert store.size() == 1


def test_store_redelivers_after_previous_pop():
    store = ExecutionMissionStore()
    mission = build_mission()

    store.push(
        mission
    )

    assert store.pop() is mission
    assert store.size() == 0

    redelivered = store.redeliver(
        mission
    )

    assert redelivered is mission
    assert store.size() == 1
    assert store.pop() is mission


def test_store_redelivery_does_not_duplicate_queued_mission():
    store = ExecutionMissionStore()
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

    assert first is mission
    assert second is mission
    assert store.size() == 1