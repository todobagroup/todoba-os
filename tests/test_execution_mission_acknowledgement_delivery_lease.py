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
from backend.trading.execution.execution_mission_delivery_lease import (
    ExecutionMissionDeliveryLease,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
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


MISSION_ID = "proof073-ack-001"
AGENT_ID = "trusted-agent-001"


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Proof073 ACK Lease",
        created_at="2026-08-07T12:00:00Z",
        expires_at="2026-08-07T13:00:00Z",
        sequence=1,
    )


def build_acknowledgement() -> (
    ExecutionMissionAcknowledgement
):
    return ExecutionMissionAcknowledgement(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        sequence=1,
        status="ACCEPTED",
        acknowledged_at="2026-08-07T12:00:05Z",
    )


def build_lease() -> ExecutionMissionDeliveryLease:
    return ExecutionMissionDeliveryLease(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        leased_at="2026-08-07T12:00:00Z",
        expires_at="2026-08-07T12:00:30Z",
    )


def test_acknowledgement_releases_delivery_lease(
    tmp_path: Path,
) -> None:
    registry = ExecutionMissionRegistry()

    registry.register(
        ExecutionMissionRecord(
            mission=build_mission()
        )
    )

    lifecycle_service = (
        ExecutionMissionLifecycleService(
            registry
        )
    )

    acknowledgement_store = (
        ExecutionMissionAcknowledgementStore()
    )

    acknowledgement = build_acknowledgement()

    acknowledgement_store.push(
        acknowledgement
    )

    persistence = ExecutionMissionEvidencePersistence(
        tmp_path / "evidence.json"
    )

    persistence.save(
        acknowledgement
    )

    lease_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    lease_registry.acquire(
        build_lease()
    )

    processor = (
        ExecutionMissionAcknowledgementProcessor(
            store=acknowledgement_store,
            lifecycle_service=lifecycle_service,
            persistence=persistence,
            lease_registry=lease_registry,
        )
    )

    result = processor.process_next()

    assert result is not None

    assert lease_registry.get(
        MISSION_ID
    ) is None

    assert lease_registry.size() == 0

    assert persistence.size() == 0


def test_acknowledgement_keeps_delivery_lease_when_lifecycle_fails(
    tmp_path: Path,
) -> None:
    registry = ExecutionMissionRegistry()

    lifecycle_service = (
        ExecutionMissionLifecycleService(
            registry
        )
    )

    acknowledgement_store = (
        ExecutionMissionAcknowledgementStore()
    )

    acknowledgement = build_acknowledgement()

    acknowledgement_store.push(
        acknowledgement
    )

    persistence = ExecutionMissionEvidencePersistence(
        tmp_path / "evidence.json"
    )

    persistence.save(
        acknowledgement
    )

    lease_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    lease_registry.acquire(
        build_lease()
    )

    processor = (
        ExecutionMissionAcknowledgementProcessor(
            store=acknowledgement_store,
            lifecycle_service=lifecycle_service,
            persistence=persistence,
            lease_registry=lease_registry,
        )
    )

    with pytest.raises(
        ValueError,
        match="Execution mission record not found.",
    ):
        processor.process_next()

    assert lease_registry.get(
        MISSION_ID
    ) is not None

    assert lease_registry.size() == 1

    assert persistence.size() == 1