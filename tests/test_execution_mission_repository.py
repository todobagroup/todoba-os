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


def test_execution_mission_repository_stores_and_reads():

    mission = ExecutionMission(
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