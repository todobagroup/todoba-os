from backend.main import (
    execution_mission_record_persistence,
    execution_mission_record_recovery,
    execution_mission_registry,
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


def test_main_composes_execution_mission_record_recovery() -> None:
    assert isinstance(
        execution_mission_registry,
        ExecutionMissionRegistry,
    )

    assert isinstance(
        execution_mission_record_persistence,
        ExecutionMissionRecordPersistence,
    )

    assert isinstance(
        execution_mission_record_recovery,
        ExecutionMissionRecordRecovery,
    )

    assert (
        execution_mission_record_recovery.persistence
        is execution_mission_record_persistence
    )

    assert (
        execution_mission_record_recovery.registry
        is execution_mission_registry
    )