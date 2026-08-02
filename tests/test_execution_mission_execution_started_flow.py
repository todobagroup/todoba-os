from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from backend.trading.execution.execution_mission import (
    ExecutionMission,
)

from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)

from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)

from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)

from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)

from backend.trading.execution.execution_mission_execution_started import (
    ExecutionMissionExecutionStarted,
)

from backend.trading.execution.execution_mission_execution_started_store import (
    ExecutionMissionExecutionStartedStore,
)

from backend.trading.execution.execution_mission_execution_started_processor import (
    ExecutionMissionExecutionStartedProcessor,
)


def test_execution_mission_execution_started_flow():

    mission = ExecutionMission(
        mission_id="execution-started-flow-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Execution Started Flow",
        created_at="2026-08-02T00:00:00Z",
        expires_at="2026-08-03T00:00:00Z",
        sequence=1,
    )


    registry = ExecutionMissionRegistry()

    registry.register(
        ExecutionMissionRecord(
            mission=mission
        )
    )


    lifecycle_service = (
        ExecutionMissionLifecycleService(
            registry
        )
    )


    store = (
        ExecutionMissionExecutionStartedStore()
    )


    evidence = ExecutionMissionExecutionStarted(
        mission_id=mission.mission_id,
        agent_id=mission.agent_id,
        sequence=1,
        started_at="2026-08-02T00:02:00Z",
    )


    store.push(
        evidence
    )


    processor = (
        ExecutionMissionExecutionStartedProcessor(
            store=store,
            lifecycle_service=lifecycle_service,
        )
    )


    result = processor.process_next()


    assert result is not None

    assert result.status == (
        ExecutionMissionStatus.EXECUTING
    )

    assert result.started_at == (
        "2026-08-02T00:02:00Z"
    )