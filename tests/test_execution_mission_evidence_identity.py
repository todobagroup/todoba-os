import pytest

from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)
from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)
from backend.trading.execution.execution_mission_completed import (
    ExecutionMissionCompleted,
)
from backend.trading.execution.execution_mission_evidence_identity import (
    ExecutionMissionEvidenceIdentity,
)
from backend.trading.execution.execution_mission_execution_started import (
    ExecutionMissionExecutionStarted,
)
from backend.trading.execution.execution_mission_failed import (
    ExecutionMissionFailed,
)


def test_acknowledgement_identity() -> None:
    evidence = ExecutionMissionAcknowledgement(
        mission_id="mission-001",
        agent_id="trusted-agent-001",
        sequence=1,
        status="ACCEPTED",
        acknowledged_at="2026-08-07T00:00:00Z",
    )

    assert ExecutionMissionEvidenceIdentity.build(
        evidence
    ) == "ACKNOWLEDGEMENT:mission-001"


def test_execution_started_identity() -> None:
    evidence = ExecutionMissionExecutionStarted(
        mission_id="mission-001",
        agent_id="trusted-agent-001",
        sequence=1,
        started_at="2026-08-07T00:01:00Z",
    )

    assert ExecutionMissionEvidenceIdentity.build(
        evidence
    ) == "EXECUTION_STARTED:mission-001"


def test_completed_identity() -> None:
    evidence = ExecutionMissionCompleted(
        mission_id="mission-001",
        agent_id="trusted-agent-001",
        sequence=1,
        completed_at="2026-08-07T00:02:00Z",
    )

    assert ExecutionMissionEvidenceIdentity.build(
        evidence
    ) == "COMPLETED:mission-001"


def test_failed_identity() -> None:
    evidence = ExecutionMissionFailed(
        mission_id="mission-001",
        agent_id="trusted-agent-001",
        sequence=1,
        failed_at="2026-08-07T00:02:00Z",
        failure_reason="broker_rejected_order",
    )

    assert ExecutionMissionEvidenceIdentity.build(
        evidence
    ) == "FAILED:mission-001"


def test_broker_execution_identity_uses_trade_tickets() -> None:
    evidence = BrokerExecutionEvidence(
        mission_id="mission-001",
        agent_id="trusted-agent-001",
        success=True,
        retcode=10009,
        order_ticket=500001,
        deal_ticket=600001,
        execution_price=4050.0,
        comment="Request executed",
        completed_at="2026-08-07T00:03:00Z",
    )

    assert ExecutionMissionEvidenceIdentity.build(
        evidence
    ) == (
        "BROKER_EXECUTION:"
        "mission-001:"
        "500001:"
        "600001"
    )


def test_identity_rejects_unsupported_evidence() -> None:
    with pytest.raises(
        TypeError,
        match="Unsupported execution mission evidence.",
    ):
        ExecutionMissionEvidenceIdentity.build(
            object()
        )