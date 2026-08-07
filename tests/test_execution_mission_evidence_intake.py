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


def build_intake(
    persistence: ExecutionMissionEvidencePersistence,
) -> tuple[
    ExecutionMissionEvidenceIntake,
    ExecutionMissionAcknowledgementStore,
]:
    acknowledgement_store = (
        ExecutionMissionAcknowledgementStore()
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
    )

    return intake, acknowledgement_store


def build_acknowledgement() -> (
    ExecutionMissionAcknowledgement
):
    return ExecutionMissionAcknowledgement(
        mission_id="intake-001",
        agent_id="trusted-agent-001",
        sequence=1,
        status="ACCEPTED",
        acknowledged_at="2026-08-07T00:00:00Z",
    )


def test_intake_persists_before_pushing_to_store(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path
        / "execution_mission_evidence.json"
    )

    intake, acknowledgement_store = build_intake(
        persistence
    )

    acknowledgement = build_acknowledgement()

    received = intake.receive(
        acknowledgement
    )

    assert received == acknowledgement
    assert persistence.size() == 1
    assert acknowledgement_store.size() == 1
    assert acknowledgement_store.pop() == (
        acknowledgement
    )


def test_intake_does_not_push_when_persistence_fails(
    tmp_path: Path,
) -> None:
    persistence = FailingEvidencePersistence(
        tmp_path
        / "execution_mission_evidence.json"
    )

    intake, acknowledgement_store = build_intake(
        persistence
    )

    acknowledgement = build_acknowledgement()

    with pytest.raises(
        RuntimeError,
        match="Evidence persistence failed.",
    ):
        intake.receive(
            acknowledgement
        )

    assert acknowledgement_store.size() == 0