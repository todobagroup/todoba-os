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

from backend.trading.execution.execution_mission_completed import (
    ExecutionMissionCompleted,
)

from backend.trading.execution.execution_mission_completed_store import (
    ExecutionMissionCompletedStore,
)

from backend.trading.execution.execution_mission_completed_processor import (
    ExecutionMissionCompletedProcessor,
)


def test_execution_mission_completed_flow():

    mission = ExecutionMission(
        mission_id="completed-flow-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Completed Flow",
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
        ExecutionMissionCompletedStore()
    )


    evidence = ExecutionMissionCompleted(
        mission_id=mission.mission_id,
        agent_id=mission.agent_id,
        sequence=1,
        completed_at="2026-08-02T00:03:00Z",
    )


    store.push(
        evidence
    )


    processor = (
        ExecutionMissionCompletedProcessor(
            store=store,
            lifecycle_service=lifecycle_service,
        )
    )


    result = processor.process_next()


    assert result is not None

    assert result.status == (
        ExecutionMissionStatus.COMPLETED
    )

    assert result.completed_at == (
        "2026-08-02T00:03:00Z"
    )