from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)

from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)

from backend.trading.execution.broker_execution_evidence_processor import (
    BrokerExecutionEvidenceProcessor,
)

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


def test_broker_execution_evidence_full_flow():

    mission = ExecutionMission(
        mission_id="proof053-flow-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="Proof053 Flow",
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

    lifecycle_service = (
        ExecutionMissionLifecycleService(
            registry
        )
    )

    evidence_store = (
        BrokerExecutionEvidenceStore()
    )

    evidence_store.push(
        BrokerExecutionEvidence(
            mission_id=mission.mission_id,
            agent_id=mission.agent_id,
            success=True,
            retcode=10009,
            order_ticket=123456,
            deal_ticket=789012,
            execution_price=4038.8,
            comment="Broker accepted",
            completed_at="2026-08-04T00:03:00Z",
        )
    )

    processor = (
        BrokerExecutionEvidenceProcessor(
            store=evidence_store,
            lifecycle_service=lifecycle_service,
        )
    )

    result = processor.process_next()

    assert result is not None

    assert result.status == (
        ExecutionMissionStatus.COMPLETED
    )

    assert result.completed_at == (
        "2026-08-04T00:03:00Z"
    )

    assert evidence_store.size() == 0