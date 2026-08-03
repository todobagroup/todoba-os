from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)

from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)


def test_broker_execution_evidence_store_push_and_pop():

    store = BrokerExecutionEvidenceStore()

    evidence = BrokerExecutionEvidence(
        mission_id="proof049-001",
        agent_id="trusted-agent-001",
        success=True,
        retcode=10009,
        order_ticket=922753906,
        deal_ticket=1114153808,
        execution_price=4038.8,
        comment="Request executed",
        completed_at="2026-08-04T00:00:00",
    )

    stored = store.push(
        evidence
    )

    assert stored == evidence

    assert store.size() == 1

    result = store.pop()

    assert result == evidence

    assert store.size() == 0


def test_broker_execution_evidence_store_empty_pop():

    store = BrokerExecutionEvidenceStore()

    result = store.pop()

    assert result is None