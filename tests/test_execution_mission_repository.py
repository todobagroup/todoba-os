import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id="repository-001",
        agent_id="trusted-agent-001",
        account_fingerprint="account-test",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4090.0,
        tp=4120.0,
        magic_number=10001,
        comment="TODOBA",
        created_at="2026-07-29T00:00:00",
        expires_at="2026-07-29T01:00:00",
        sequence=1,
    )


def test_execution_mission_repository_stores_and_reads():
    mission = build_mission()

    repository = ExecutionMissionRepository()

    result = repository.save(
        mission
    )

    assert result == mission
    assert repository.size() == 1

    stored = repository.get(
        "repository-001"
    )

    assert stored == mission
    assert repository.all() == [
        mission
    ]


def test_execution_mission_repository_removes_existing_mission():
    mission = build_mission()

    repository = ExecutionMissionRepository()

    repository.save(
        mission
    )

    removed = repository.remove(
        mission.mission_id
    )

    assert removed is True
    assert repository.get(
        mission.mission_id
    ) is None
    assert repository.size() == 0
    assert repository.all() == []


def test_execution_mission_repository_remove_missing_mission_returns_false():
    repository = ExecutionMissionRepository()

    removed = repository.remove(
        "missing-mission"
    )

    assert removed is False
    assert repository.size() == 0