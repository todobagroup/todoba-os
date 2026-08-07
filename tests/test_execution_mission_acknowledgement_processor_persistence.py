from pathlib import Path

import pytest

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)
from backend.trading.execution.execution_mission_acknowledgement_processor import (
    ExecutionMissionAcknowledgementProcessor,
)
from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)
from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
)
from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)


def build_acknowledgement() -> (
    ExecutionMissionAcknowledgement
):
    return ExecutionMissionAcknowledgement(
        mission_id="ack-persistence-001",
        agent_id="trusted-agent-001",
        sequence=1,
        status="ACCEPTED",
        acknowledged_at="2026-08-07T00:00:00Z",
    )


def build_registry(
    include_record: bool,
) -> ExecutionMissionRegistry:
    registry = ExecutionMissionRegistry()

    if include_record:
        mission = ExecutionMission(
            mission_id="ack-persistence-001",
            agent_id="trusted-agent-001",
            account_fingerprint="demo-account",
            symbol="XAUUSD",
            order_type="BUY",
            volume=0.01,
            entry=None,
            sl=4100.0,
            tp=4200.0,
            magic_number=10001,
            comment="TODOBA Processor Persistence",
            created_at="2026-08-07T00:00:00Z",
            expires_at="2026-08-07T01:00:00Z",
            sequence=1,
        )

        registry.register(
            ExecutionMissionRecord(
                mission=mission
            )
        )

    return registry


def test_processor_removes_evidence_after_success(
    tmp_path: Path,
) -> None:
    evidence = build_acknowledgement()

    store = ExecutionMissionAcknowledgementStore()
    store.push(
        evidence
    )

    persistence = ExecutionMissionEvidencePersistence(
        tmp_path
        / "execution_mission_evidence.json"
    )
    persistence.save(
        evidence
    )

    processor = ExecutionMissionAcknowledgementProcessor(
        store=store,
        lifecycle_service=(
            ExecutionMissionLifecycleService(
                build_registry(
                    include_record=True
                )
            )
        ),
        persistence=persistence,
    )

    result = processor.process_next()

    assert result is not None
    assert persistence.size() == 0


def test_processor_keeps_evidence_when_lifecycle_fails(
    tmp_path: Path,
) -> None:
    evidence = build_acknowledgement()

    store = ExecutionMissionAcknowledgementStore()
    store.push(
        evidence
    )

    persistence = ExecutionMissionEvidencePersistence(
        tmp_path
        / "execution_mission_evidence.json"
    )
    persistence.save(
        evidence
    )

    processor = ExecutionMissionAcknowledgementProcessor(
        store=store,
        lifecycle_service=(
            ExecutionMissionLifecycleService(
                build_registry(
                    include_record=False
                )
            )
        ),
        persistence=persistence,
    )

    with pytest.raises(
        ValueError,
        match="Execution mission record not found.",
    ):
        processor.process_next()

    assert persistence.size() == 1