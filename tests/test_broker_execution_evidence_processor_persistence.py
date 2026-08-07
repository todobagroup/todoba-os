from pathlib import Path

import pytest

from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)
from backend.trading.execution.broker_execution_evidence_processor import (
    BrokerExecutionEvidenceProcessor,
)
from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)
from backend.trading.execution.execution_mission import (
    ExecutionMission,
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


def build_evidence(
    success: bool,
) -> BrokerExecutionEvidence:
    return BrokerExecutionEvidence(
        mission_id="broker-persistence-001",
        agent_id="trusted-agent-001",
        success=success,
        retcode=10009 if success else 10021,
        order_ticket=123456,
        deal_ticket=654321,
        execution_price=4105.5,
        comment=(
            "Request executed"
            if success
            else "Broker rejected order"
        ),
        completed_at="2026-08-07T00:00:00Z",
    )


def build_registry(
    include_record: bool,
) -> ExecutionMissionRegistry:
    registry = ExecutionMissionRegistry()

    if include_record:
        mission = ExecutionMission(
            mission_id="broker-persistence-001",
            agent_id="trusted-agent-001",
            account_fingerprint="demo-account",
            symbol="XAUUSD",
            order_type="BUY",
            volume=0.01,
            entry=None,
            sl=4100.0,
            tp=4200.0,
            magic_number=10001,
            comment="TODOBA Broker Persistence",
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


def build_processor(
    tmp_path: Path,
    evidence: BrokerExecutionEvidence,
    include_record: bool,
) -> tuple[
    BrokerExecutionEvidenceProcessor,
    ExecutionMissionEvidencePersistence,
]:
    store = BrokerExecutionEvidenceStore()
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

    processor = BrokerExecutionEvidenceProcessor(
        store=store,
        lifecycle_service=(
            ExecutionMissionLifecycleService(
                build_registry(
                    include_record=include_record
                )
            )
        ),
        persistence=persistence,
    )

    return processor, persistence


def test_processor_removes_success_evidence_after_completion(
    tmp_path: Path,
) -> None:
    processor, persistence = build_processor(
        tmp_path=tmp_path,
        evidence=build_evidence(
            success=True
        ),
        include_record=True,
    )

    result = processor.process_next()

    assert result is not None
    assert persistence.size() == 0


def test_processor_removes_failed_evidence_after_failure_transition(
    tmp_path: Path,
) -> None:
    processor, persistence = build_processor(
        tmp_path=tmp_path,
        evidence=build_evidence(
            success=False
        ),
        include_record=True,
    )

    result = processor.process_next()

    assert result is not None
    assert persistence.size() == 0


def test_processor_keeps_evidence_when_lifecycle_fails(
    tmp_path: Path,
) -> None:
    processor, persistence = build_processor(
        tmp_path=tmp_path,
        evidence=build_evidence(
            success=True
        ),
        include_record=False,
    )

    with pytest.raises(
        ValueError,
        match="Execution mission record not found.",
    ):
        processor.process_next()

    assert persistence.size() == 1