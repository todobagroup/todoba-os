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

from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)

from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)

from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)

from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)

from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)

from backend.trading.execution.execution_mission_acknowledgement_processor import (
    ExecutionMissionAcknowledgementProcessor,
)


def test_execution_mission_trusted_agent_flow():

    mission = ExecutionMission(
        mission_id="agent-flow-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Trusted Agent Flow",
        created_at="2026-08-02T00:00:00Z",
        expires_at="2026-08-03T00:00:00Z",
        sequence=1,
    )


    mission_store = ExecutionMissionStore()

    delivery_bridge = (
        ExecutionMissionDeliveryBridge(
            mission_store
        )
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


    delivered = (
        delivery_bridge.deliver(
            mission
        )
    )

    assert delivered == mission

    assert mission_store.size() == 1


    agent_received = (
        mission_store.pop()
    )

    assert agent_received == mission


    acknowledgement_store = (
        ExecutionMissionAcknowledgementStore()
    )


    acknowledgement = ExecutionMissionAcknowledgement(
        mission_id=mission.mission_id,
        agent_id=mission.agent_id,
        sequence=1,
        status="acknowledged",
        acknowledged_at="2026-08-02T00:01:00Z",
    )


    acknowledgement_store.push(
        acknowledgement
    )


    processor = (
        ExecutionMissionAcknowledgementProcessor(
            store=acknowledgement_store,
            lifecycle_service=lifecycle_service,
        )
    )


    result = processor.process_next()


    assert result is not None

    assert result.status.name == (
        "ACKNOWLEDGED"
    )