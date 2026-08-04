from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)

from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)

from backend.trading.execution.broker_execution_evidence_processor import (
    BrokerExecutionEvidenceProcessor,
)

from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)

from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)

from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)

from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


def build_service():

    mission = ExecutionMission(
        mission_id="broker-evidence-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="Proof053",
        created_at="2026-08-04T00:00:00Z",
        expires_at="2026-08-05T00:00:00Z",
        sequence=1,
    )

    registry = ExecutionMissionRegistry()

    registry.register(
        ExecutionMissionRecord(
            mission=mission
        )
    )

    return (
        mission,
        ExecutionMissionLifecycleService(
            registry
        )
    )


def test_processor_completes_mission_from_success_evidence():

    mission, lifecycle_service = build_service()

    store = BrokerExecutionEvidenceStore()

    store.push(
        BrokerExecutionEvidence(
            mission_id=mission.mission_id,
            agent_id=mission.agent_id,
            success=True,
            retcode=10009,
            order_ticket=123,
            deal_ticket=456,
            execution_price=4038.8,
            comment="Request executed",
            completed_at="2026-08-04T00:01:00Z",
        )
    )

    processor = BrokerExecutionEvidenceProcessor(
        store=store,
        lifecycle_service=lifecycle_service,
    )

    result = processor.process_next()

    assert result.status == (
        ExecutionMissionStatus.COMPLETED
    )


def test_processor_fails_mission_from_failed_evidence():

    mission, lifecycle_service = build_service()

    store = BrokerExecutionEvidenceStore()

    store.push(
        BrokerExecutionEvidence(
            mission_id=mission.mission_id,
            agent_id=mission.agent_id,
            success=False,
            retcode=10030,
            order_ticket=0,
            deal_ticket=0,
            execution_price=0,
            comment="Broker rejected",
            completed_at="2026-08-04T00:02:00Z",
        )
    )

    processor = BrokerExecutionEvidenceProcessor(
        store=store,
        lifecycle_service=lifecycle_service,
    )

    result = processor.process_next()

    assert result.status == (
        ExecutionMissionStatus.FAILED
    )