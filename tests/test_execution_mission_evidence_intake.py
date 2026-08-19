from pathlib import Path

import pytest

from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)
from backend.trading.execution.execution_mission import (
    ExecutionMission,
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
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)


MISSION_ID = "intake-001"
AGENT_ID = "trusted-agent-001"


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


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA intake test",
        sequence=1,
        created_at="2026-08-07T00:00:00Z",
        expires_at="2026-08-07T00:05:00Z",
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

    mission_registry = ExecutionMissionRegistry()

    mission_registry.register(
        ExecutionMissionRecord(
            mission=build_mission()
        )
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
        mission_registry=mission_registry,
    )

    return intake, acknowledgement_store


def build_acknowledgement() -> (
    ExecutionMissionAcknowledgement
):
    return ExecutionMissionAcknowledgement(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
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