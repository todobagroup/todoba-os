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
from backend.trading.control.control_mission_registry import (
    ControlMissionRegistry,
)
from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
)


def build_record() -> ControlMissionRecord:
    mission = ControlMission(
        mission_id="control-001",
        agent_id="trusted-agent-001",
        account_fingerprint="account-test",
        action=ControlAction.FLATTEN_ALL,
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
        delivered_at="2026-08-15T00:00:01Z",
        delivery_attempt_count=1,
        acknowledged_at="2026-08-15T00:00:02Z",
        started_at="2026-08-15T00:00:03Z",
        completed_at="2026-08-15T00:00:04Z",
        matched_position_count=3,
        closed_position_count=3,
        matched_pending_order_count=2,
        canceled_pending_order_count=2,
        failed_item_count=0,
    )


def test_record_persistence_saves_and_restores(
    tmp_path,
) -> None:
    registry = ControlMissionRegistry()
    record = build_record()

    registry.register(
        record
    )

    storage_path = (
        tmp_path
        / "control_mission_records.json"
    )

    persistence = ControlMissionRecordPersistence(
        storage_path
    )

    persistence.save(
        registry
    )

    restored_registry = ControlMissionRegistry()

    assert persistence.restore(
        restored_registry
    ) == 1

    restored = restored_registry.get(
        record.mission.mission_id
    )

    assert restored is not None
    assert restored.mission == record.mission
    assert restored.status is ControlMissionStatus.COMPLETED
    assert restored.delivery_attempt_count == 1
    assert restored.acknowledged_at == (
        "2026-08-15T00:00:02Z"
    )
    assert restored.closed_position_count == 3
    assert restored.canceled_pending_order_count == 2
    assert restored.failed_item_count == 0


def test_record_persistence_replaces_temporary_file(
    tmp_path,
) -> None:
    registry = ControlMissionRegistry()
    registry.register(
        build_record()
    )

    storage_path = (
        tmp_path
        / "control_mission_records.json"
    )

    ControlMissionRecordPersistence(
        storage_path
    ).save(
        registry
    )

    temporary_path = storage_path.with_suffix(
        storage_path.suffix + ".tmp"
    )

    assert storage_path.exists()
    assert not temporary_path.exists()


def test_record_restore_missing_file_returns_zero(
    tmp_path,
) -> None:
    persistence = ControlMissionRecordPersistence(
        tmp_path
        / "missing-control-records.json"
    )

    assert persistence.restore(
        ControlMissionRegistry()
    ) == 0