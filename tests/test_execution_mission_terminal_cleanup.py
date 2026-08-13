from pathlib import Path

import pytest

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_delivery_lease import (
    ExecutionMissionDeliveryLease,
)
from backend.trading.execution.execution_mission_delivery_lease_persistence import (
    ExecutionMissionDeliveryLeasePersistence,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)
from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)
from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


MISSION_ID = "proof168-terminal-cleanup"
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
        comment="TODOBA Terminal Cleanup",
        created_at="2026-08-13T00:00:00Z",
        expires_at="2026-08-13T01:00:00Z",
        sequence=168001,
    )


def build_service(
    tmp_path: Path,
) -> tuple[
    ExecutionMissionLifecycleService,
    ExecutionMissionRegistry,
    ExecutionMissionRepository,
    ExecutionMissionPersistence,
    ExecutionMissionDeliveryLeaseRegistry,
    ExecutionMissionDeliveryLeasePersistence,
]:
    mission = build_mission()

    mission_registry = ExecutionMissionRegistry()

    mission_registry.register(
        ExecutionMissionRecord(
            mission=mission
        )
    )

    repository = ExecutionMissionRepository()

    repository.save(
        mission
    )

    mission_persistence = ExecutionMissionPersistence(
        tmp_path / "missions.json"
    )

    mission_persistence.save(
        repository
    )

    lease_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    lease_registry.acquire(
        ExecutionMissionDeliveryLease(
            mission_id=MISSION_ID,
            agent_id=AGENT_ID,
            leased_at="2026-08-13T00:00:00Z",
            expires_at="2026-08-13T00:00:30Z",
        )
    )

    lease_persistence = (
        ExecutionMissionDeliveryLeasePersistence(
            tmp_path / "delivery_leases.json"
        )
    )

    lease_persistence.save(
        lease_registry
    )

    service = ExecutionMissionLifecycleService(
        mission_registry,
        repository=repository,
        mission_persistence=mission_persistence,
        lease_registry=lease_registry,
        lease_persistence=lease_persistence,
    )

    return (
        service,
        mission_registry,
        repository,
        mission_persistence,
        lease_registry,
        lease_persistence,
    )


@pytest.mark.parametrize(
    "terminal_action",
    [
        "completed",
        "failed",
    ],
)
def test_terminal_transition_cleans_mission_and_lease(
    tmp_path: Path,
    terminal_action: str,
) -> None:
    (
        service,
        mission_registry,
        repository,
        mission_persistence,
        lease_registry,
        lease_persistence,
    ) = build_service(
        tmp_path
    )

    if terminal_action == "completed":
        record = service.complete_execution(
            mission_id=MISSION_ID,
            completed_at="2026-08-13T00:00:10Z",
        )

        assert record.status == (
            ExecutionMissionStatus.COMPLETED
        )
    else:
        record = service.fail_execution(
            mission_id=MISSION_ID,
            failed_at="2026-08-13T00:00:10Z",
            failure_reason="Safety Guard rejected mission.",
        )

        assert record.status == (
            ExecutionMissionStatus.FAILED
        )
        assert record.failure_reason == (
            "Safety Guard rejected mission."
        )

    assert mission_registry.get(
        MISSION_ID
    ) is record

    assert repository.get(
        MISSION_ID
    ) is None

    assert lease_registry.get(
        MISSION_ID
    ) is None

    restored_repository = (
        ExecutionMissionRepository()
    )

    assert mission_persistence.restore(
        restored_repository
    ) == 0

    restored_lease_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    assert lease_persistence.restore(
        restored_lease_registry
    ) == 0