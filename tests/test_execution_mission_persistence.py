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

from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)


def test_execution_mission_persistence_save_and_restore(
    tmp_path,
):

    mission = ExecutionMission(
        mission_id="persistence-001",
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

    repository.save(
        mission
    )

    persistence = ExecutionMissionPersistence(
        tmp_path / "execution_missions.json"
    )

    persistence.save(
        repository
    )

    restored_repository = (
        ExecutionMissionRepository()
    )

    restored_count = persistence.restore(
        restored_repository
    )

    assert restored_count == 1

    assert restored_repository.size() == 1

    restored = restored_repository.get(
        "persistence-001"
    )

    assert restored == mission