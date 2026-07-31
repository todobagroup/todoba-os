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

from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)

from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


def test_execution_mission_full_lifecycle_flow():

    mission = ExecutionMission(
        mission_id="full-flow-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Full Lifecycle",
        created_at="2026-07-31T00:00:00Z",
        expires_at="2026-08-01T00:00:00Z",
        sequence=1,
    )

    record = ExecutionMissionRecord(
        mission=mission
    )

    registry = ExecutionMissionRegistry()

    registry.register(
        record
    )

    lifecycle_service = (
        ExecutionMissionLifecycleService(
            registry
        )
    )


    acknowledged = (
        lifecycle_service.acknowledge(
            mission_id="full-flow-001",
            acknowledged_at=(
                "2026-07-31T00:01:00Z"
            ),
        )
    )

    assert acknowledged.status == (
        ExecutionMissionStatus.ACKNOWLEDGED
    )


    executing = (
        lifecycle_service.start_execution(
            mission_id="full-flow-001",
            started_at=(
                "2026-07-31T00:02:00Z"
            ),
        )
    )

    assert executing.status == (
        ExecutionMissionStatus.EXECUTING
    )


    completed = (
        lifecycle_service.complete_execution(
            mission_id="full-flow-001",
            completed_at=(
                "2026-07-31T00:03:00Z"
            ),
        )
    )

    assert completed.status == (
        ExecutionMissionStatus.COMPLETED
    )


    assert registry.size() == 1