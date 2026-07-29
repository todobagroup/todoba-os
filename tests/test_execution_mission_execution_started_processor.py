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

from backend.trading.execution.execution_mission_execution_started import (
    ExecutionMissionExecutionStarted,
)

from backend.trading.execution.execution_mission_execution_started_store import (
    ExecutionMissionExecutionStartedStore,
)

from backend.trading.execution.execution_mission_execution_started_processor import (
    ExecutionMissionExecutionStartedProcessor,
)

from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


def test_execution_started_processor_updates_execution_state():

    mission = ExecutionMission(
        mission_id="execution-start-processor-001",
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

    started_store = (
        ExecutionMissionExecutionStartedStore()
    )

    started_store.push(
        ExecutionMissionExecutionStarted(
            mission_id="execution-start-processor-001",
            agent_id="trusted-agent-001",
            sequence=1,
            started_at="2026-07-29T00:25:00",
        )
    )

    processor = (
        ExecutionMissionExecutionStartedProcessor(
            store=started_store,
            lifecycle_service=lifecycle_service,
        )
    )

    result = processor.process_next()

    assert result == record

    assert result.status == (
        ExecutionMissionStatus.EXECUTING
    )

    assert result.started_at == (
        "2026-07-29T00:25:00"
    )

    assert started_store.size() == 0