from backend.trading.execution.execution_result_evidence_adapter import (
    ExecutionResultEvidenceAdapter,
)

from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)


def test_execution_result_adapter_creates_broker_evidence():

    evidence = (
        ExecutionResultEvidenceAdapter.create_evidence(
            mission_id="proof052-001",
            agent_id="trusted-agent-001",
            success=True,
            retcode=10009,
            order_ticket=123456,
            deal_ticket=789012,
            execution_price=4038.8,
            comment="Request executed",
            completed_at="2026-08-04T00:00:00Z",
        )
    )

    assert isinstance(
        evidence,
        BrokerExecutionEvidence,
    )

    assert evidence.mission_id == (
        "proof052-001"
    )

    assert evidence.agent_id == (
        "trusted-agent-001"
    )

    assert evidence.order_ticket == (
        123456
    )

    assert evidence.deal_ticket == (
        789012
    )

    assert evidence.execution_price == (
        4038.8
    )

    assert evidence.success is True