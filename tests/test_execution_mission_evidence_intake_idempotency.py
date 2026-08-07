from pathlib import Path

import pytest

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
from backend.trading.execution.execution_mission_evidence_intake import (
    ExecutionMissionEvidenceIntake,
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


class FailingEvidencePersistence(
    ExecutionMissionEvidencePersistence
):
    def save(
        self,
        evidence: object,
    ) -> None:
        raise RuntimeError(
            "Evidence persistence failed."
        )


def build_acknowledgement() -> (
    ExecutionMissionAcknowledgement
):
    return ExecutionMissionAcknowledgement(
        mission_id="idempotency-001",
        agent_id="trusted-agent-001",
        sequence=1,
        status="ACCEPTED",
        acknowledged_at="2026-08-07T00:00:00Z",
    )


def build_intake(
    persistence: ExecutionMissionEvidencePersistence,
) -> tuple[
    ExecutionMissionEvidenceIntake,
    ExecutionMissionAcknowledgementStore,
    ExecutionMissionEvidenceIdempotencyRegistry,
]:
    acknowledgement_store = (
        ExecutionMissionAcknowledgementStore()
    )

    registry = (
        ExecutionMissionEvidenceIdempotencyRegistry()
    )

    intake = ExecutionMissionEvidenceIntake(
        persistence=persistence,
        acknowledgement_store=(
            acknowledgement_store
        ),
        execution_started_store=(
            ExecutionMissionExecutionStartedStore()
        ),
        completed_store=(
            ExecutionMissionCompletedStore()
        ),
        failed_store=(
            ExecutionMissionFailedStore()
        ),
        broker_evidence_store=(
            BrokerExecutionEvidenceStore()
        ),
        idempotency_registry=registry,
    )

    return (
        intake,
        acknowledgement_store,
        registry,
    )


def test_intake_accepts_first_evidence(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path
        / "execution_mission_evidence.json"
    )

    intake, store, registry = build_intake(
        persistence
    )

    evidence = build_acknowledgement()

    result = intake.receive(
        evidence
    )

    assert result == evidence
    assert persistence.size() == 1
    assert store.size() == 1
    assert registry.size() == 1


def test_intake_rejects_duplicate_evidence(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path
        / "execution_mission_evidence.json"
    )

    intake, store, registry = build_intake(
        persistence
    )

    evidence = build_acknowledgement()

    first_result = intake.receive(
        evidence
    )

    duplicate_result = intake.receive(
        evidence
    )

    assert first_result == evidence
    assert duplicate_result is None

    assert persistence.size() == 1
    assert store.size() == 1
    assert registry.size() == 1


def test_intake_does_not_register_when_persistence_fails(
    tmp_path: Path,
) -> None:
    persistence = FailingEvidencePersistence(
        tmp_path
        / "execution_mission_evidence.json"
    )

    intake, store, registry = build_intake(
        persistence
    )

    evidence = build_acknowledgement()

    with pytest.raises(
        RuntimeError,
        match="Evidence persistence failed.",
    ):
        intake.receive(
            evidence
        )

    assert store.size() == 0
    assert registry.size() == 0