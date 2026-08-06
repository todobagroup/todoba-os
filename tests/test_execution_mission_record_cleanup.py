from pathlib import Path

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_record_cleanup import (
    ExecutionMissionRecordCleanup,
)
from backend.trading.execution.execution_mission_record_persistence import (
    ExecutionMissionRecordPersistence,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)


def build_record(
    mission_id: str,
) -> ExecutionMissionRecord:
    mission = ExecutionMission(
        mission_id=mission_id,
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Record Cleanup",
        created_at="2026-08-06T00:00:00Z",
        expires_at="2026-08-06T01:00:00Z",
        sequence=1,
    )

    return ExecutionMissionRecord(
        mission=mission
    )


def test_cleanup_removes_selected_records_and_persists(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "execution_mission_records.json"
    )

    registry = ExecutionMissionRegistry()

    registry.register(
        build_record(
            "cleanup-001"
        )
    )

    registry.register(
        build_record(
            "cleanup-002"
        )
    )

    persistence = ExecutionMissionRecordPersistence(
        storage_path
    )

    persistence.save(
        registry
    )

    cleanup = ExecutionMissionRecordCleanup(
        registry=registry,
        persistence=persistence,
    )

    removed = cleanup.cleanup(
        [
            "cleanup-001",
            "missing",
        ]
    )

    assert removed == 1
    assert registry.size() == 1
    assert registry.get(
        "cleanup-001"
    ) is None
    assert registry.get(
        "cleanup-002"
    ) is not None

    restored_registry = ExecutionMissionRegistry()

    restored_count = persistence.restore(
        restored_registry
    )

    assert restored_count == 1
    assert restored_registry.get(
        "cleanup-001"
    ) is None
    assert restored_registry.get(
        "cleanup-002"
    ) is not None


def test_cleanup_without_matches_does_not_remove_records(
    tmp_path: Path,
) -> None:
    registry = ExecutionMissionRegistry()

    registry.register(
        build_record(
            "cleanup-003"
        )
    )

    persistence = ExecutionMissionRecordPersistence(
        tmp_path
        / "execution_mission_records.json"
    )

    cleanup = ExecutionMissionRecordCleanup(
        registry=registry,
        persistence=persistence,
    )

    removed = cleanup.cleanup(
        [
            "missing",
        ]
    )

    assert removed == 0
    assert registry.size() == 1