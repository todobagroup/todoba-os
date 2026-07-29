import sys
from pathlib import Path

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

from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


def test_execution_completed_processor_updates_completed_state():

    mission = ExecutionMission(
        mission_id="execution-completed-processor-001",
        agent_id="trusted-agent-001",
        account_fingerprint="account-test",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4090.0,
        tp=4120.0,
        magic_number=10001,
        comment="TODOBA",
        created_at="2026-07-29T00:00:00",
        expires_at="2026-07-29T01:00:00",
        sequence=1,
    )

    registry = ExecutionMissionRegistry()

    record = ExecutionMissionRecord(
        mission=mission
    )

    registry.register(
        record
    )

    lifecycle_service = (
        ExecutionMissionLifecycleService(
            registry
        )
    )

    completed_store = (
        ExecutionMissionCompletedStore()
    )

    completed_store.push(
        ExecutionMissionCompleted(
            mission_id="execution-completed-processor-001",
            agent_id="trusted-agent-001",
            sequence=1,
            completed_at="2026-07-29T00:30:00",
        )
    )

    processor = (
        ExecutionMissionCompletedProcessor(
            store=completed_store,
            lifecycle_service=lifecycle_service,
        )
    )

    result = processor.process_next()

    assert result == record

    assert result.status == (
        ExecutionMissionStatus.COMPLETED
    )

    assert result.completed_at == (
        "2026-07-29T00:30:00"
    )

    assert completed_store.size() == 0