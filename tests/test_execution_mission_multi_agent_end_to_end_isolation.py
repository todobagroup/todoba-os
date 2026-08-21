"""
TODOBA Multi-Agent End-to-End Execution Isolation Proof

CAP 3G proof:

Two Trusted Agents and two MT5 account ownership domains
must be able to coexist in the same execution runtime
without cross-agent or cross-account contamination.

Proof boundary:

- Agent-scoped mission delivery
- Evidence ownership enforcement
- Independent acknowledgement lifecycle
- Independent execution-started lifecycle
- Independent completion lifecycle
- Terminal state isolation
"""

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
from backend.trading.execution.execution_mission_acknowledgement_processor import (
    ExecutionMissionAcknowledgementProcessor,
)
from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)
from backend.trading.execution.execution_mission_completed import (
    ExecutionMissionCompleted,
)
from backend.trading.execution.execution_mission_completed_processor import (
    ExecutionMissionCompletedProcessor,
)
from backend.trading.execution.execution_mission_completed_store import (
    ExecutionMissionCompletedStore,
)
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_evidence_intake import (
    ExecutionMissionEvidenceIntake,
)
from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
)
from backend.trading.execution.execution_mission_execution_started import (
    ExecutionMissionExecutionStarted,
)
from backend.trading.execution.execution_mission_execution_started_processor import (
    ExecutionMissionExecutionStartedProcessor,
)
from backend.trading.execution.execution_mission_execution_started_store import (
    ExecutionMissionExecutionStartedStore,
)
from backend.trading.execution.execution_mission_failed_store import (
    ExecutionMissionFailedStore,
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
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)


AGENT_A = "trusted-agent-a"
AGENT_B = "trusted-agent-b"

ACCOUNT_A = "broker-a:100001"
ACCOUNT_B = "broker-b:200002"

MISSION_A = "multi-agent-e2e-a"
MISSION_B = "multi-agent-e2e-b"


def build_mission(
    *,
    mission_id: str,
    agent_id: str,
    account_fingerprint: str,
    sequence: int,
) -> ExecutionMission:
    return ExecutionMission(
        mission_id=mission_id,
        agent_id=agent_id,
        account_fingerprint=account_fingerprint,
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA multi-agent isolation",
        created_at="2026-08-21T00:00:00Z",
        expires_at="2099-01-01T00:00:00Z",
        sequence=sequence,
    )


def assert_status(
    *,
    registry: ExecutionMissionRegistry,
    mission_id: str,
    expected_status: ExecutionMissionStatus,
) -> None:
    record = registry.get(
        mission_id
    )

    assert record is not None

    assert record.status == (
        expected_status
    )


def test_two_agents_complete_independent_end_to_end_lifecycles(
    tmp_path: Path,
) -> None:
    mission_a = build_mission(
        mission_id=MISSION_A,
        agent_id=AGENT_A,
        account_fingerprint=ACCOUNT_A,
        sequence=301001,
    )

    mission_b = build_mission(
        mission_id=MISSION_B,
        agent_id=AGENT_B,
        account_fingerprint=ACCOUNT_B,
        sequence=301002,
    )

    registry = ExecutionMissionRegistry()

    registry.register(
        ExecutionMissionRecord(
            mission=mission_a
        )
    )

    registry.register(
        ExecutionMissionRecord(
            mission=mission_b
        )
    )

    lifecycle_service = (
        ExecutionMissionLifecycleService(
            registry
        )
    )

    mission_store = ExecutionMissionStore()

    delivery_bridge = (
        ExecutionMissionDeliveryBridge(
            mission_store
        )
    )

    delivery_bridge.deliver(
        mission_a
    )

    delivery_bridge.deliver(
        mission_b
    )

    assert mission_store.size() == 2

    received_b = (
        mission_store.pop_for_agent(
            AGENT_B
        )
    )

    assert received_b == mission_b
    assert received_b.agent_id == AGENT_B
    assert (
        received_b.account_fingerprint
        == ACCOUNT_B
    )

    assert mission_store.size() == 1

    assert (
        mission_store.pop_for_agent(
            AGENT_B
        )
        is None
    )

    assert mission_store.size() == 1

    received_a = (
        mission_store.pop_for_agent(
            AGENT_A
        )
    )

    assert received_a == mission_a
    assert received_a.agent_id == AGENT_A
    assert (
        received_a.account_fingerprint
        == ACCOUNT_A
    )

    assert mission_store.size() == 0

    assert_status(
        registry=registry,
        mission_id=MISSION_A,
        expected_status=(
            ExecutionMissionStatus.CREATED
        ),
    )

    assert_status(
        registry=registry,
        mission_id=MISSION_B,
        expected_status=(
            ExecutionMissionStatus.CREATED
        ),
    )

    evidence_persistence = (
        ExecutionMissionEvidencePersistence(
            tmp_path
            / "execution_mission_evidence.json"
        )
    )

    acknowledgement_store = (
        ExecutionMissionAcknowledgementStore()
    )

    execution_started_store = (
        ExecutionMissionExecutionStartedStore()
    )

    completed_store = (
        ExecutionMissionCompletedStore()
    )

    failed_store = (
        ExecutionMissionFailedStore()
    )

    broker_evidence_store = (
        BrokerExecutionEvidenceStore()
    )

    intake = ExecutionMissionEvidenceIntake(
        persistence=evidence_persistence,
        acknowledgement_store=(
            acknowledgement_store
        ),
        execution_started_store=(
            execution_started_store
        ),
        completed_store=(
            completed_store
        ),
        failed_store=failed_store,
        broker_evidence_store=(
            broker_evidence_store
        ),
        mission_registry=registry,
    )

    acknowledgement_processor = (
        ExecutionMissionAcknowledgementProcessor(
            store=acknowledgement_store,
            lifecycle_service=lifecycle_service,
        )
    )

    execution_started_processor = (
        ExecutionMissionExecutionStartedProcessor(
            store=execution_started_store,
            lifecycle_service=lifecycle_service,
        )
    )

    completed_processor = (
        ExecutionMissionCompletedProcessor(
            store=completed_store,
            lifecycle_service=lifecycle_service,
        )
    )

    cross_agent_evidence = (
        ExecutionMissionAcknowledgement(
            mission_id=MISSION_A,
            agent_id=AGENT_B,
            sequence=301001,
            status="acknowledged",
            acknowledged_at=(
                "2026-08-21T00:01:00Z"
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "Execution mission evidence does not belong "
            "to mission Agent."
        ),
    ):
        intake.receive(
            cross_agent_evidence
        )

    assert evidence_persistence.size() == 0
    assert acknowledgement_store.size() == 0

    assert_status(
        registry=registry,
        mission_id=MISSION_A,
        expected_status=(
            ExecutionMissionStatus.CREATED
        ),
    )

    assert_status(
        registry=registry,
        mission_id=MISSION_B,
        expected_status=(
            ExecutionMissionStatus.CREATED
        ),
    )

    intake.receive(
        ExecutionMissionAcknowledgement(
            mission_id=MISSION_A,
            agent_id=AGENT_A,
            sequence=301001,
            status="acknowledged",
            acknowledged_at=(
                "2026-08-21T00:02:00Z"
            ),
        )
    )

    acknowledged_a = (
        acknowledgement_processor.process_next()
    )

    assert acknowledged_a is not None
    assert acknowledged_a.mission.mission_id == (
        MISSION_A
    )

    assert_status(
        registry=registry,
        mission_id=MISSION_A,
        expected_status=(
            ExecutionMissionStatus.ACKNOWLEDGED
        ),
    )

    assert_status(
        registry=registry,
        mission_id=MISSION_B,
        expected_status=(
            ExecutionMissionStatus.CREATED
        ),
    )

    intake.receive(
        ExecutionMissionAcknowledgement(
            mission_id=MISSION_B,
            agent_id=AGENT_B,
            sequence=301002,
            status="acknowledged",
            acknowledged_at=(
                "2026-08-21T00:03:00Z"
            ),
        )
    )

    acknowledged_b = (
        acknowledgement_processor.process_next()
    )

    assert acknowledged_b is not None
    assert acknowledged_b.mission.mission_id == (
        MISSION_B
    )

    assert_status(
        registry=registry,
        mission_id=MISSION_A,
        expected_status=(
            ExecutionMissionStatus.ACKNOWLEDGED
        ),
    )

    assert_status(
        registry=registry,
        mission_id=MISSION_B,
        expected_status=(
            ExecutionMissionStatus.ACKNOWLEDGED
        ),
    )

    intake.receive(
        ExecutionMissionExecutionStarted(
            mission_id=MISSION_A,
            agent_id=AGENT_A,
            sequence=301001,
            started_at=(
                "2026-08-21T00:04:00Z"
            ),
        )
    )

    executing_a = (
        execution_started_processor.process_next()
    )

    assert executing_a is not None
    assert executing_a.mission.mission_id == (
        MISSION_A
    )

    assert_status(
        registry=registry,
        mission_id=MISSION_A,
        expected_status=(
            ExecutionMissionStatus.EXECUTING
        ),
    )

    assert_status(
        registry=registry,
        mission_id=MISSION_B,
        expected_status=(
            ExecutionMissionStatus.ACKNOWLEDGED
        ),
    )

    intake.receive(
        ExecutionMissionExecutionStarted(
            mission_id=MISSION_B,
            agent_id=AGENT_B,
            sequence=301002,
            started_at=(
                "2026-08-21T00:05:00Z"
            ),
        )
    )

    executing_b = (
        execution_started_processor.process_next()
    )

    assert executing_b is not None
    assert executing_b.mission.mission_id == (
        MISSION_B
    )

    assert_status(
        registry=registry,
        mission_id=MISSION_A,
        expected_status=(
            ExecutionMissionStatus.EXECUTING
        ),
    )

    assert_status(
        registry=registry,
        mission_id=MISSION_B,
        expected_status=(
            ExecutionMissionStatus.EXECUTING
        ),
    )

    intake.receive(
        ExecutionMissionCompleted(
            mission_id=MISSION_A,
            agent_id=AGENT_A,
            sequence=301001,
            completed_at=(
                "2026-08-21T00:06:00Z"
            ),
        )
    )

    completed_a = (
        completed_processor.process_next()
    )

    assert completed_a is not None
    assert completed_a.mission.mission_id == (
        MISSION_A
    )

    assert_status(
        registry=registry,
        mission_id=MISSION_A,
        expected_status=(
            ExecutionMissionStatus.COMPLETED
        ),
    )

    assert_status(
        registry=registry,
        mission_id=MISSION_B,
        expected_status=(
            ExecutionMissionStatus.EXECUTING
        ),
    )

    intake.receive(
        ExecutionMissionCompleted(
            mission_id=MISSION_B,
            agent_id=AGENT_B,
            sequence=301002,
            completed_at=(
                "2026-08-21T00:07:00Z"
            ),
        )
    )

    completed_b = (
        completed_processor.process_next()
    )

    assert completed_b is not None
    assert completed_b.mission.mission_id == (
        MISSION_B
    )

    assert_status(
        registry=registry,
        mission_id=MISSION_A,
        expected_status=(
            ExecutionMissionStatus.COMPLETED
        ),
    )

    assert_status(
        registry=registry,
        mission_id=MISSION_B,
        expected_status=(
            ExecutionMissionStatus.COMPLETED
        ),
    )

    final_a = registry.get(
        MISSION_A
    )

    final_b = registry.get(
        MISSION_B
    )

    assert final_a is not None
    assert final_b is not None

    assert final_a is not final_b

    assert final_a.mission.agent_id == (
        AGENT_A
    )

    assert final_b.mission.agent_id == (
        AGENT_B
    )

    assert (
        final_a.mission.account_fingerprint
        == ACCOUNT_A
    )

    assert (
        final_b.mission.account_fingerprint
        == ACCOUNT_B
    )

    assert final_a.completed_at == (
        "2026-08-21T00:06:00Z"
    )

    assert final_b.completed_at == (
        "2026-08-21T00:07:00Z"
    )

    assert registry.size() == 2

    assert acknowledgement_store.size() == 0
    assert execution_started_store.size() == 0
    assert completed_store.size() == 0