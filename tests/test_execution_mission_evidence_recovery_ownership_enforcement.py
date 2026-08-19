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


MISSION_ID = "recovery-ownership-001"
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
        comment="TODOBA recovery ownership",
        sequence=1,
        created_at="2026-08-19T00:00:00Z",
        expires_at="2026-08-19T00:05:00Z",
    )


def build_evidence(
    *,
    mission_id: str = MISSION_ID,
    agent_id: str = MISSION_AGENT_ID,
) -> ExecutionMissionAcknowledgement:
    return ExecutionMissionAcknowledgement(
        mission_id=mission_id,
        agent_id=agent_id,
        sequence=1,
        status="ACCEPTED",
        acknowledged_at="2026-08-19T00:01:00Z",
    )


def build_stores() -> dict[str, object]:
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


def test_recovery_restores_evidence_owned_by_mission_agent(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path / "execution_mission_evidence.json"
    )

    evidence = build_evidence()

    persistence.save(
        evidence
    )

    mission_registry = ExecutionMissionRegistry()

    mission_registry.register(
        ExecutionMissionRecord(
            mission=build_mission()
        )
    )

    stores = build_stores()

    restored = persistence.restore(
        **stores,
        mission_registry=mission_registry,
    )

    assert restored == 1

    assert (
        stores["acknowledgement_store"].pop()
        == evidence
    )


def test_recovery_rejects_unknown_mission_before_ram_and_idempotency(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path / "execution_mission_evidence.json"
    )

    persistence.save(
        build_evidence(
            mission_id="unknown-mission"
        )
    )

    mission_registry = ExecutionMissionRegistry()

    idempotency_registry = (
        ExecutionMissionEvidenceIdempotencyRegistry()
    )

    stores = build_stores()

    with pytest.raises(
        ValueError,
        match="Execution mission record not found.",
    ):
        persistence.restore(
            **stores,
            mission_registry=mission_registry,
            idempotency_registry=(
                idempotency_registry
            ),
        )

    assert (
        stores["acknowledgement_store"].size()
        == 0
    )

    assert idempotency_registry.size() == 0


def test_recovery_rejects_cross_agent_before_ram_and_idempotency(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path / "execution_mission_evidence.json"
    )

    persistence.save(
        build_evidence(
            agent_id=OTHER_AGENT_ID
        )
    )

    mission_registry = ExecutionMissionRegistry()

    mission_registry.register(
        ExecutionMissionRecord(
            mission=build_mission(
                agent_id=MISSION_AGENT_ID
            )
        )
    )

    idempotency_registry = (
        ExecutionMissionEvidenceIdempotencyRegistry()
    )

    stores = build_stores()

    with pytest.raises(
        ValueError,
        match=(
            "Execution mission evidence does not belong "
            "to mission Agent."
        ),
    ):
        persistence.restore(
            **stores,
            mission_registry=mission_registry,
            idempotency_registry=(
                idempotency_registry
            ),
        )

    assert (
        stores["acknowledgement_store"].size()
        == 0
    )

    assert idempotency_registry.size() == 0