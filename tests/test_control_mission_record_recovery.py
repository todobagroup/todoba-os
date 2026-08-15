from pathlib import Path

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_record import (
    ControlMissionRecord,
)
from backend.trading.control.control_mission_record_persistence import (
    ControlMissionRecordPersistence,
)
from backend.trading.control.control_mission_record_recovery import (
    ControlMissionRecordRecovery,
)
from backend.trading.control.control_mission_registry import (
    ControlMissionRegistry,
)
from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
)


def build_record() -> ControlMissionRecord:
    mission = ControlMission(
        mission_id="control-record-recovery-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        action=ControlAction.CLOSE_GREEN,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=5414928751,
        created_at="2026-08-15T00:00:00Z",
        expires_at="2026-08-15T00:01:00Z",
        sequence=1,
    )

    return ControlMissionRecord(
        mission=mission,
        status=ControlMissionStatus.COMPLETED,
        delivered_at="2026-08-15T00:00:10Z",
        acknowledged_at="2026-08-15T00:00:20Z",
        started_at="2026-08-15T00:00:30Z",
        completed_at="2026-08-15T00:00:40Z",
    )


def test_record_recovery_restores_persisted_records(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "control_mission_records.json"
    )

    persistence = ControlMissionRecordPersistence(
        storage_path
    )

    source_registry = ControlMissionRegistry()

    source_registry.register(
        build_record()
    )

    persistence.save(
        source_registry
    )

    restored_registry = ControlMissionRegistry()

    recovery = ControlMissionRecordRecovery(
        persistence=persistence,
        registry=restored_registry,
    )

    restored_count = recovery.restore()

    assert restored_count == 1
    assert restored_registry.size() == 1

    restored = restored_registry.get(
        "control-record-recovery-001"
    )

    assert restored is not None
    assert restored.status is (
        ControlMissionStatus.COMPLETED
    )
    assert restored.completed_at == (
        "2026-08-15T00:00:40Z"
    )


def test_record_recovery_returns_zero_without_storage(
    tmp_path: Path,
) -> None:
    persistence = ControlMissionRecordPersistence(
        tmp_path / "missing.json"
    )

    registry = ControlMissionRegistry()

    recovery = ControlMissionRecordRecovery(
        persistence=persistence,
        registry=registry,
    )

    assert recovery.restore() == 0
    assert registry.size() == 0