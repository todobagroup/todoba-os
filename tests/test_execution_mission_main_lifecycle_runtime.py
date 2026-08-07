from backend.main import (
    broker_execution_evidence_processor,
    execution_mission_acknowledgement_processor,
    execution_mission_completed_processor,
    execution_mission_execution_started_processor,
    execution_mission_failed_processor,
    execution_mission_lifecycle_scheduler,
    execution_mission_lifecycle_service,
)
from backend.trading.execution.broker_execution_evidence_processor import (
    BrokerExecutionEvidenceProcessor,
)
from backend.trading.execution.execution_mission_acknowledgement_processor import (
    ExecutionMissionAcknowledgementProcessor,
)
from backend.trading.execution.execution_mission_completed_processor import (
    ExecutionMissionCompletedProcessor,
)
from backend.trading.execution.execution_mission_execution_started_processor import (
    ExecutionMissionExecutionStartedProcessor,
)
from backend.trading.execution.execution_mission_failed_processor import (
    ExecutionMissionFailedProcessor,
)
from backend.trading.execution.execution_mission_lifecycle_scheduler import (
    ExecutionMissionLifecycleScheduler,
)
from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)


def test_main_composes_execution_mission_lifecycle_runtime() -> None:
    assert isinstance(
        execution_mission_lifecycle_service,
        ExecutionMissionLifecycleService,
    )

    assert isinstance(
        execution_mission_acknowledgement_processor,
        ExecutionMissionAcknowledgementProcessor,
    )

    assert isinstance(
        execution_mission_execution_started_processor,
        ExecutionMissionExecutionStartedProcessor,
    )

    assert isinstance(
        execution_mission_completed_processor,
        ExecutionMissionCompletedProcessor,
    )

    assert isinstance(
        execution_mission_failed_processor,
        ExecutionMissionFailedProcessor,
    )

    assert isinstance(
        broker_execution_evidence_processor,
        BrokerExecutionEvidenceProcessor,
    )

    assert isinstance(
        execution_mission_lifecycle_scheduler,
        ExecutionMissionLifecycleScheduler,
    )

    assert execution_mission_lifecycle_scheduler.processors == [
        execution_mission_acknowledgement_processor,
        execution_mission_execution_started_processor,
        execution_mission_completed_processor,
        execution_mission_failed_processor,
        broker_execution_evidence_processor,
    ]