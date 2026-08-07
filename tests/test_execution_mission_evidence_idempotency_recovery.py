from pathlib import Path

from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)
from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)
from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)
from backend.trading.execution.execution_mission_completed_store import (
    ExecutionMissionCompletedStore,
)
from backend.trading.execution.execution_mission_evidence_idempotency_registry import (
    ExecutionMissionEvidenceIdempotencyRegistry,
)
from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
)
from backend.trading.execution.execution_mission_execution_started_store import (
    ExecutionMissionExecutionStartedStore,
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


def build_acknowledgement():
    return ExecutionMissionAcknowledgement(
        mission_id="recovery-001",
        agent_id="trusted-agent-001",
        sequence=1,
        status="ACCEPTED",
        acknowledged_at="2026-08-07T00:00:00Z",
    )


def test_restore_recovers_evidence_identity(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path / "evidence.json"
    )

    evidence = build_acknowledgement()

    persistence.save(
        evidence
    )

    stores = build_stores()

    registry = (
        ExecutionMissionEvidenceIdempotencyRegistry()
    )

    restored = persistence.restore(
        **stores,
        idempotency_registry=registry,
    )

    assert restored == 1

    assert (
        stores["acknowledgement_store"].size()
        == 1
    )

    assert registry.size() == 1


def test_restore_does_not_enqueue_duplicate_evidence(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path / "evidence.json"
    )

    evidence = build_acknowledgement()

    persistence.save(
        evidence
    )

    persistence.save(
        evidence
    )

    assert persistence.size() == 2

    stores = build_stores()

    registry = (
        ExecutionMissionEvidenceIdempotencyRegistry()
    )

    restored = persistence.restore(
        **stores,
        idempotency_registry=registry,
    )

    assert restored == 1

    assert (
        stores["acknowledgement_store"].size()
        == 1
    )

    assert registry.size() == 1