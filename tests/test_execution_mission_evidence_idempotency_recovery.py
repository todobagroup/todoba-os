from pathlib import Path

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
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)


MISSION_ID = "recovery-001"
AGENT_ID = "trusted-agent-001"


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
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        sequence=1,
        status="ACCEPTED",
        acknowledged_at="2026-08-07T00:00:00Z",
    )


def build_mission_registry():
    mission = ExecutionMission(
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
        comment="TODOBA evidence recovery",
        sequence=1,
        created_at="2026-08-07T00:00:00Z",
        expires_at="2026-08-07T00:05:00Z",
    )

    mission_registry = ExecutionMissionRegistry()

    mission_registry.register(
        ExecutionMissionRecord(
            mission=mission
        )
    )

    return mission_registry


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

    mission_registry = build_mission_registry()

    idempotency_registry = (
        ExecutionMissionEvidenceIdempotencyRegistry()
    )

    restored = persistence.restore(
        **stores,
        mission_registry=mission_registry,
        idempotency_registry=idempotency_registry,
    )

    assert restored == 1

    assert (
        stores["acknowledgement_store"].size()
        == 1
    )

    assert idempotency_registry.size() == 1


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

    mission_registry = build_mission_registry()

    idempotency_registry = (
        ExecutionMissionEvidenceIdempotencyRegistry()
    )

    restored = persistence.restore(
        **stores,
        mission_registry=mission_registry,
        idempotency_registry=idempotency_registry,
    )

    assert restored == 1

    assert (
        stores["acknowledgement_store"].size()
        == 1
    )

    assert idempotency_registry.size() == 1