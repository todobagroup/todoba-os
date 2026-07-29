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

from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)

from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)

from backend.trading.execution.execution_mission_acknowledgement_processor import (
    ExecutionMissionAcknowledgementProcessor,
)

from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


def test_acknowledgement_processor_updates_mission_lifecycle():

    mission = ExecutionMission(
        mission_id="ack-processor-001",
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

    acknowledgement_store = (
        ExecutionMissionAcknowledgementStore()
    )

    acknowledgement_store.push(
        ExecutionMissionAcknowledgement(
            mission_id="ack-processor-001",
            agent_id="trusted-agent-001",
            sequence=1,
            status="ACCEPTED",
            acknowledged_at="2026-07-29T00:15:00",
        )
    )

    processor = (
        ExecutionMissionAcknowledgementProcessor(
            store=acknowledgement_store,
            lifecycle_service=lifecycle_service,
        )
    )

    result = processor.process_next()

    assert result == record

    assert result.status == (
        ExecutionMissionStatus.ACKNOWLEDGED
    )

    assert result.acknowledged_at == (
        "2026-07-29T00:15:00"
    )

    assert acknowledgement_store.size() == 0