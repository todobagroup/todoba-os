from pathlib import Path

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_record_persistence import (
    ExecutionMissionRecordPersistence,
)
from backend.trading.execution.execution_mission_record_recovery import (
    ExecutionMissionRecordRecovery,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


def build_record() -> ExecutionMissionRecord:
    mission = ExecutionMission(
        mission_id="record-recovery-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Record Recovery",
        created_at="2026-08-06T00:00:00Z",
        expires_at="2026-08-06T01:00:00Z",
        sequence=1,
    )

    return ExecutionMissionRecord(
        mission=mission,
        status=ExecutionMissionStatus.COMPLETED,
        delivered_at="2026-08-06T00:01:00Z",
        acknowledged_at="2026-08-06T00:02:00Z",
        started_at="2026-08-06T00:03:00Z",
        completed_at="2026-08-06T00:04:00Z",
    )


def test_record_recovery_restores_persisted_records(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "execution_mission_records.json"
    )

    persistence = ExecutionMissionRecordPersistence(
        storage_path
    )

    source_registry = ExecutionMissionRegistry()

    source_registry.register(
        build_record()
    )

    persistence.save(
        source_registry
    )

    restored_registry = ExecutionMissionRegistry()

    recovery = ExecutionMissionRecordRecovery(
        persistence=persistence,
        registry=restored_registry,
    )

    restored_count = recovery.restore()

    assert restored_count == 1
    assert restored_registry.size() == 1

    restored = restored_registry.get(
        "record-recovery-001"
    )

    assert restored is not None
    assert restored.status == (
        ExecutionMissionStatus.COMPLETED
    )
    assert restored.completed_at == (
        "2026-08-06T00:04:00Z"
    )


def test_record_recovery_returns_zero_without_storage(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionRecordPersistence(
        tmp_path
        / "missing.json"
    )

    registry = ExecutionMissionRegistry()

    recovery = ExecutionMissionRecordRecovery(
        persistence=persistence,
        registry=registry,
    )

    assert recovery.restore() == 0
    assert registry.size() == 0