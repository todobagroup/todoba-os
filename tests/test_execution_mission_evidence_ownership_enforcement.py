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


MISSION_ID = "ownership-001"
MISSION_AGENT_ID = "trusted-agent-a"
OTHER_AGENT_ID = "trusted-agent-b"


def build_mission(
    *,
    agent_id: str = MISSION_AGENT_ID,
) -> ExecutionMission:
    return ExecutionMission(
        mission_id=MISSION_ID,
        agent_id=agent_id,
        account_fingerprint="account-a",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA evidence ownership",
        sequence=1,
        created_at="2026-08-19T00:00:00Z",
        expires_at="2026-08-19T00:05:00Z",
    )


def build_acknowledgement(
    *,
    mission_id: str = MISSION_ID,
    agent_id: str = MISSION_AGENT_ID,
) -> ExecutionMissionAcknowledgement:
    return ExecutionMissionAcknowledgement(
        mission_id=mission_id,
        agent_id=agent_id,
        sequence=1,
        status="ACCEPTED",
        acknowledged_at="2026-08-19T00:00:00Z",
    )


def build_intake(
    *,
    tmp_path: Path,
    registry: ExecutionMissionRegistry,
) -> tuple[
    ExecutionMissionEvidenceIntake,
    ExecutionMissionEvidencePersistence,
    ExecutionMissionAcknowledgementStore,
]:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path / "execution_mission_evidence.json"
    )

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
        mission_registry=registry,
    )

    return (
        intake,
        persistence,
        acknowledgement_store,
    )


def test_intake_accepts_evidence_owned_by_mission_agent(
    tmp_path: Path,
) -> None:
    registry = ExecutionMissionRegistry()

    mission = build_mission()

    registry.register(
        ExecutionMissionRecord(
            mission=mission
        )
    )

    (
        intake,
        persistence,
        acknowledgement_store,
    ) = build_intake(
        tmp_path=tmp_path,
        registry=registry,
    )

    acknowledgement = build_acknowledgement()

    received = intake.receive(
        acknowledgement
    )

    assert received == acknowledgement
    assert persistence.size() == 1
    assert acknowledgement_store.size() == 1


def test_intake_rejects_cross_agent_mission_evidence_before_storage(
    tmp_path: Path,
) -> None:
    registry = ExecutionMissionRegistry()

    mission = build_mission(
        agent_id=MISSION_AGENT_ID
    )

    registry.register(
        ExecutionMissionRecord(
            mission=mission
        )
    )

    (
        intake,
        persistence,
        acknowledgement_store,
    ) = build_intake(
        tmp_path=tmp_path,
        registry=registry,
    )

    acknowledgement = build_acknowledgement(
        agent_id=OTHER_AGENT_ID
    )

    with pytest.raises(
        ValueError,
        match=(
            "Execution mission evidence does not belong "
            "to mission Agent."
        ),
    ):
        intake.receive(
            acknowledgement
        )

    assert persistence.size() == 0
    assert acknowledgement_store.size() == 0


def test_intake_rejects_unknown_mission_before_storage(
    tmp_path: Path,
) -> None:
    registry = ExecutionMissionRegistry()

    (
        intake,
        persistence,
        acknowledgement_store,
    ) = build_intake(
        tmp_path=tmp_path,
        registry=registry,
    )

    acknowledgement = build_acknowledgement(
        mission_id="unknown-mission"
    )

    with pytest.raises(
        ValueError,
        match="Execution mission record not found.",
    ):
        intake.receive(
            acknowledgement
        )

    assert persistence.size() == 0
    assert acknowledgement_store.size() == 0