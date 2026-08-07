from pathlib import Path

from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)
from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)
from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)
from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)
from backend.trading.execution.execution_mission_completed import (
    ExecutionMissionCompleted,
)
from backend.trading.execution.execution_mission_completed_store import (
    ExecutionMissionCompletedStore,
)
from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
)
from backend.trading.execution.execution_mission_execution_started import (
    ExecutionMissionExecutionStarted,
)
from backend.trading.execution.execution_mission_execution_started_store import (
    ExecutionMissionExecutionStartedStore,
)
from backend.trading.execution.execution_mission_failed import (
    ExecutionMissionFailed,
)
from backend.trading.execution.execution_mission_failed_store import (
    ExecutionMissionFailedStore,
)


def build_stores():
    return {
        "acknowledgement_store": (
            ExecutionMissionAcknowledgementStore()
        ),
        "execution_started_store": (
            ExecutionMissionExecutionStartedStore()
        ),
        "completed_store": (
            ExecutionMissionCompletedStore()
        ),
        "failed_store": (
            ExecutionMissionFailedStore()
        ),
        "broker_evidence_store": (
            BrokerExecutionEvidenceStore()
        ),
    }


def test_persistence_saves_and_restores_all_evidence_types(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path / "execution_mission_evidence.json"
    )

    acknowledgement = ExecutionMissionAcknowledgement(
        mission_id="mission-001",
        agent_id="agent-001",
        sequence=1,
        status="ACKNOWLEDGED",
        acknowledged_at="2026-08-07T00:00:01Z",
    )

    execution_started = ExecutionMissionExecutionStarted(
        mission_id="mission-002",
        agent_id="agent-001",
        sequence=2,
        started_at="2026-08-07T00:00:02Z",
    )

    completed = ExecutionMissionCompleted(
        mission_id="mission-003",
        agent_id="agent-001",
        sequence=3,
        completed_at="2026-08-07T00:00:03Z",
    )

    failed = ExecutionMissionFailed(
        mission_id="mission-004",
        agent_id="agent-001",
        sequence=4,
        failed_at="2026-08-07T00:00:04Z",
        failure_reason="broker rejected order",
    )

    broker_evidence = BrokerExecutionEvidence(
        mission_id="mission-005",
        agent_id="agent-001",
        success=True,
        retcode=10009,
        order_ticket=123456,
        deal_ticket=654321,
        execution_price=4105.5,
        comment="executed",
        completed_at="2026-08-07T00:00:05Z",
    )

    evidence = [
        acknowledgement,
        execution_started,
        completed,
        failed,
        broker_evidence,
    ]

    for item in evidence:
        persistence.save(
            item
        )

    assert persistence.size() == 5

    stores = build_stores()

    restored = persistence.restore(
        **stores
    )

    assert restored == 5

    assert (
        stores["acknowledgement_store"].pop()
        == acknowledgement
    )

    assert (
        stores["execution_started_store"].pop()
        == execution_started
    )

    assert (
        stores["completed_store"].pop()
        == completed
    )

    assert (
        stores["failed_store"].pop()
        == failed
    )

    assert (
        stores["broker_evidence_store"].pop()
        == broker_evidence
    )


def test_persistence_remove_removes_processed_evidence(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path / "execution_mission_evidence.json"
    )

    evidence = ExecutionMissionCompleted(
        mission_id="mission-remove",
        agent_id="agent-001",
        sequence=1,
        completed_at="2026-08-07T00:00:00Z",
    )

    persistence.save(
        evidence
    )

    assert persistence.size() == 1

    removed = persistence.remove(
        evidence
    )

    assert removed is True
    assert persistence.size() == 0


def test_persistence_remove_missing_evidence_returns_false(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path / "execution_mission_evidence.json"
    )

    evidence = ExecutionMissionFailed(
        mission_id="mission-missing",
        agent_id="agent-001",
        sequence=1,
        failed_at="2026-08-07T00:00:00Z",
        failure_reason="test",
    )

    removed = persistence.remove(
        evidence
    )

    assert removed is False
    assert persistence.size() == 0