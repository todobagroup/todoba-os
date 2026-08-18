from pathlib import Path

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_persistence import (
    ControlMissionPersistence,
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
from backend.trading.control.control_mission_repository import (
    ControlMissionRepository,
)
from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
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
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)


SECURITY_SEQUENCE = 42


def build_execution_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id="security-persistence-execution-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA security persistence",
        created_at="2026-08-18T00:00:00Z",
        expires_at="2026-08-18T01:00:00Z",
        sequence=168001,
        security_sequence=SECURITY_SEQUENCE,
    )


def build_control_mission() -> ControlMission:
    return ControlMission(
        mission_id="security-persistence-control-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        action=ControlAction.CLOSE_ALL_POSITIONS,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=168,
        created_at="2026-08-18T00:00:00Z",
        expires_at="2026-08-18T01:00:00Z",
        sequence=168002,
        security_sequence=SECURITY_SEQUENCE,
    )


def test_execution_mission_persistence_preserves_security_sequence(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "execution_missions.json"
    )

    persistence = ExecutionMissionPersistence(
        storage_path
    )

    source_repository = (
        ExecutionMissionRepository()
    )

    mission = build_execution_mission()

    source_repository.save(
        mission
    )

    persistence.save(
        source_repository
    )

    restored_repository = (
        ExecutionMissionRepository()
    )

    assert persistence.restore(
        restored_repository
    ) == 1

    restored = restored_repository.get(
        mission.mission_id
    )

    assert restored is not None
    assert (
        restored.security_sequence
        == SECURITY_SEQUENCE
    )


def test_execution_record_persistence_preserves_security_sequence(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "execution_mission_records.json"
    )

    persistence = (
        ExecutionMissionRecordPersistence(
            storage_path
        )
    )

    mission = build_execution_mission()

    source_registry = (
        ExecutionMissionRegistry()
    )

    source_registry.register(
        ExecutionMissionRecord(
            mission=mission
        )
    )

    persistence.save(
        source_registry
    )

    restored_registry = (
        ExecutionMissionRegistry()
    )

    assert persistence.restore(
        restored_registry
    ) == 1

    restored = restored_registry.get(
        mission.mission_id
    )

    assert restored is not None
    assert (
        restored.mission.security_sequence
        == SECURITY_SEQUENCE
    )


def test_control_mission_persistence_preserves_security_sequence(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "control_missions.json"
    )

    persistence = ControlMissionPersistence(
        storage_path
    )

    mission = build_control_mission()

    source_repository = (
        ControlMissionRepository()
    )

    source_repository.save(
        mission
    )

    persistence.save(
        source_repository
    )

    restored_repository = (
        ControlMissionRepository()
    )

    assert persistence.restore(
        restored_repository
    ) == 1

    restored = restored_repository.get(
        mission.mission_id
    )

    assert restored is not None
    assert (
        restored.security_sequence
        == SECURITY_SEQUENCE
    )


def test_control_record_persistence_preserves_security_sequence(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "control_mission_records.json"
    )

    persistence = (
        ControlMissionRecordPersistence(
            storage_path
        )
    )

    mission = build_control_mission()

    source_registry = (
        ControlMissionRegistry()
    )

    source_registry.register(
        ControlMissionRecord(
            mission=mission
        )
    )

    persistence.save(
        source_registry
    )

    restored_registry = (
        ControlMissionRegistry()
    )

    assert persistence.restore(
        restored_registry
    ) == 1

    restored = restored_registry.get(
        mission.mission_id
    )

    assert restored is not None
    assert (
        restored.mission.security_sequence
        == SECURITY_SEQUENCE
    )