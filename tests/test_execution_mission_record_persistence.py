import json
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
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


def build_record() -> ExecutionMissionRecord:
    mission = ExecutionMission(
        mission_id="record-persistence-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Record Persistence",
        created_at="2026-08-06T00:00:00Z",
        expires_at="2026-08-06T01:00:00Z",
        sequence=1,
    )

    return ExecutionMissionRecord(
        mission=mission,
        status=ExecutionMissionStatus.FAILED,
        delivered_at="2026-08-06T00:01:00Z",
        delivery_attempt_count=3,
        acknowledged_at="2026-08-06T00:02:00Z",
        started_at="2026-08-06T00:03:00Z",
        failed_at="2026-08-06T00:04:00Z",
        failure_reason="broker_rejected_order",
    )


def test_record_persistence_saves_and_restores_lifecycle(
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

    restored_count = persistence.restore(
        restored_registry
    )

    assert restored_count == 1
    assert restored_registry.size() == 1

    restored = restored_registry.get(
        "record-persistence-001"
    )

    assert restored is not None
    assert restored.mission.mission_id == (
        "record-persistence-001"
    )
    assert restored.mission.agent_id == (
        "trusted-agent-001"
    )
    assert restored.status == (
        ExecutionMissionStatus.FAILED
    )
    assert restored.delivered_at == (
        "2026-08-06T00:01:00Z"
    )
    assert restored.delivery_attempt_count == 3
    assert restored.acknowledged_at == (
        "2026-08-06T00:02:00Z"
    )
    assert restored.started_at == (
        "2026-08-06T00:03:00Z"
    )
    assert restored.completed_at is None
    assert restored.failed_at == (
        "2026-08-06T00:04:00Z"
    )
    assert restored.failure_reason == (
        "broker_rejected_order"
    )


def test_record_persistence_restores_legacy_record_with_zero_attempts(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "legacy_execution_mission_records.json"
    )

    storage_path.write_text(
        json.dumps(
            [
                {
                    "mission": {
                        "mission_id": "legacy-record-001",
                        "agent_id": "trusted-agent-001",
                        "account_fingerprint": "demo-account",
                        "symbol": "XAUUSD",
                        "order_type": "BUY",
                        "volume": 0.01,
                        "entry": None,
                        "sl": 4100.0,
                        "tp": 4200.0,
                        "magic_number": 10001,
                        "comment": "TODOBA Legacy Record",
                        "created_at": "2026-08-05T00:00:00Z",
                        "expires_at": "2026-08-05T01:00:00Z",
                        "sequence": 1,
                    },
                    "status": "CREATED",
                    "delivered_at": None,
                    "acknowledged_at": None,
                    "started_at": None,
                    "completed_at": None,
                    "failed_at": None,
                    "failure_reason": None,
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    persistence = ExecutionMissionRecordPersistence(
        storage_path
    )

    registry = ExecutionMissionRegistry()

    assert persistence.restore(
        registry
    ) == 1

    restored = registry.get(
        "legacy-record-001"
    )

    assert restored is not None
    assert restored.delivery_attempt_count == 0


def test_record_persistence_restore_without_file_returns_zero(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionRecordPersistence(
        tmp_path
        / "missing.json"
    )

    registry = ExecutionMissionRegistry()

    assert persistence.restore(
        registry
    ) == 0

    assert registry.size() == 0