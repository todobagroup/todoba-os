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


def build_mission(
    mission_id: str,
    agent_id: str,
) -> ExecutionMission:

    return ExecutionMission(
        mission_id=mission_id,
        agent_id=agent_id,
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Handshake Proof",
        created_at="2026-08-04T00:00:00Z",
        expires_at="2026-08-05T00:00:00Z",
        sequence=1,
    )


def test_trusted_agent_full_handshake_flow():

    mission = build_mission(
        "handshake-001",
        "trusted-agent-001",
    )

    store = ExecutionMissionStore()

    delivery_bridge = (
        ExecutionMissionDeliveryBridge(
            store
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

    delivery_bridge.deliver(
        mission
    )

    received = store.pop_for_agent(
        "trusted-agent-001"
    )

    assert received == mission


    acknowledgement_store = (
        ExecutionMissionAcknowledgementStore()
    )

    acknowledgement_store.push(
        ExecutionMissionAcknowledgement(
            mission_id=mission.mission_id,
            agent_id=mission.agent_id,
            sequence=mission.sequence,
            status="acknowledged",
            acknowledged_at="2026-08-04T00:01:00Z",
        )
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