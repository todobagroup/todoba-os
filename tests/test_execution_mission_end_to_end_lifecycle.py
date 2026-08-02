from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from backend.trading.execution.execution_mission import (
    ExecutionMission,
)

from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)

from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)

from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)

from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)

from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)

from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)

from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)

from backend.trading.execution.execution_mission_acknowledgement_processor import (
    ExecutionMissionAcknowledgementProcessor,
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

from backend.trading.execution.execution_mission_completed import (
    ExecutionMissionCompleted,
)

from backend.trading.execution.execution_mission_completed_store import (
    ExecutionMissionCompletedStore,
)

from backend.trading.execution.execution_mission_completed_processor import (
    ExecutionMissionCompletedProcessor,
)

from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


def test_execution_mission_end_to_end_lifecycle():

    mission = ExecutionMission(
        mission_id="e2e-flow-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA E2E Lifecycle",
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


    mission_store = ExecutionMissionStore()

    delivery_bridge = (
        ExecutionMissionDeliveryBridge(
            mission_store
        )
    )


    delivered = delivery_bridge.deliver(
        mission
    )

    assert delivered == mission


    received = mission_store.pop()

    assert received == mission


    acknowledgement_store = (
        ExecutionMissionAcknowledgementStore()
    )


    acknowledgement_store.push(
        ExecutionMissionAcknowledgement(
            mission_id=mission.mission_id,
            agent_id=mission.agent_id,
            sequence=1,
            status="acknowledged",
            acknowledged_at="2026-08-02T00:01:00Z",
        )
    )


    acknowledgement_processor = (
        ExecutionMissionAcknowledgementProcessor(
            store=acknowledgement_store,
            lifecycle_service=lifecycle_service,
        )
    )


    acknowledged = (
        acknowledgement_processor.process_next()
    )

    assert acknowledged.status == (
        ExecutionMissionStatus.ACKNOWLEDGED
    )


    execution_started_store = (
        ExecutionMissionExecutionStartedStore()
    )


    execution_started_store.push(
        ExecutionMissionExecutionStarted(
            mission_id=mission.mission_id,
            agent_id=mission.agent_id,
            sequence=1,
            started_at="2026-08-02T00:02:00Z",
        )
    )


    execution_started_processor = (
        ExecutionMissionExecutionStartedProcessor(
            store=execution_started_store,
            lifecycle_service=lifecycle_service,
        )
    )


    executing = (
        execution_started_processor.process_next()
    )


    assert executing.status == (
        ExecutionMissionStatus.EXECUTING
    )


    completed_store = (
        ExecutionMissionCompletedStore()
    )


    completed_store.push(
        ExecutionMissionCompleted(
            mission_id=mission.mission_id,
            agent_id=mission.agent_id,
            sequence=1,
            completed_at="2026-08-02T00:03:00Z",
        )
    )


    completed_processor = (
        ExecutionMissionCompletedProcessor(
            store=completed_store,
            lifecycle_service=lifecycle_service,
        )
    )


    completed = (
        completed_processor.process_next()
    )


    assert completed.status == (
        ExecutionMissionStatus.COMPLETED
    )

    assert completed.completed_at == (
        "2026-08-02T00:03:00Z"
    )