from datetime import datetime
from datetime import timezone
from pathlib import Path

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
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
from backend.trading.execution.execution_mission_delivery_redelivery_processor import (
    ExecutionMissionDeliveryRedeliveryProcessor,
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
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)


MISSION_ID = "proof076-redelivery-001"
AGENT_ID = "trusted-agent-001"


def fixed_clock() -> datetime:
    return datetime(
        2026,
        8,
        8,
        12,
        1,
        0,
        tzinfo=timezone.utc,
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
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Proof076 Redelivery",
        created_at="2026-08-08T12:00:00Z",
        expires_at="2026-08-08T13:00:00Z",
        sequence=1,
    )


def build_case(
    tmp_path: Path,
    *,
    lease_expires_at: str,
    delivery_attempt_count: int,
    include_mission: bool = True,
) -> dict:
    mission = build_mission()

    repository = ExecutionMissionRepository()

    if include_mission:
        repository.save(
            mission
        )

    store = ExecutionMissionStore()

    lease_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    lease = ExecutionMissionDeliveryLease(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        leased_at="2026-08-08T12:00:00Z",
        expires_at=lease_expires_at,
    )

    lease_registry.acquire(
        lease
    )

    lease_persistence = (
        ExecutionMissionDeliveryLeasePersistence(
            tmp_path / "delivery_leases.json"
        )
    )

    lease_persistence.save(
        lease_registry
    )

    mission_registry = ExecutionMissionRegistry()

    mission_registry.register(
        ExecutionMissionRecord(
            mission=mission,
            status=ExecutionMissionStatus.DELIVERED,
            delivered_at="2026-08-08T12:00:00Z",
            delivery_attempt_count=(
                delivery_attempt_count
            ),
        )
    )

    lifecycle_service = (
        ExecutionMissionLifecycleService(
            mission_registry
        )
    )

    processor = (
        ExecutionMissionDeliveryRedeliveryProcessor(
            repository=repository,
            delivery_bridge=(
                ExecutionMissionDeliveryBridge(
                    store
                )
            ),
            lease_registry=lease_registry,
            clock=fixed_clock,
            lease_persistence=lease_persistence,
            lifecycle_service=lifecycle_service,
            max_delivery_attempts=3,
        )
    )

    return {
        "mission": mission,
        "repository": repository,
        "store": store,
        "lease": lease,
        "lease_registry": lease_registry,
        "lease_persistence": lease_persistence,
        "mission_registry": mission_registry,
        "processor": processor,
    }


def assert_no_persisted_lease(
    case: dict,
) -> None:
    restored_registry = (
        ExecutionMissionDeliveryLeaseRegistry()
    )

    assert case[
        "lease_persistence"
    ].restore(
        restored_registry
    ) == 0


def test_expired_lease_redelivers_when_attempts_remain(
    tmp_path: Path,
) -> None:
    case = build_case(
        tmp_path,
        lease_expires_at="2026-08-08T12:00:30Z",
        delivery_attempt_count=2,
    )

    result = case["processor"].process_next()

    assert result == case["mission"]
    assert case["store"].size() == 1

    assert case["lease_registry"].get(
        MISSION_ID
    ) is None

    record = case["mission_registry"].get(
        MISSION_ID
    )

    assert record is not None
    assert record.status == (
        ExecutionMissionStatus.DELIVERED
    )
    assert record.delivery_attempt_count == 2

    assert_no_persisted_lease(
        case
    )


def test_expired_lease_fails_when_attempts_exhausted(
    tmp_path: Path,
) -> None:
    case = build_case(
        tmp_path,
        lease_expires_at="2026-08-08T12:00:30Z",
        delivery_attempt_count=3,
    )

    result = case["processor"].process_next()

    assert result is None
    assert case["store"].size() == 0

    assert case["lease_registry"].get(
        MISSION_ID
    ) is None

    record = case["mission_registry"].get(
        MISSION_ID
    )

    assert record is not None
    assert record.status == (
        ExecutionMissionStatus.FAILED
    )
    assert record.failed_at == (
        "2026-08-08T12:01:00Z"
    )
    assert record.failure_reason == (
        "Delivery attempts exhausted."
    )
    assert record.delivery_attempt_count == 3

    assert_no_persisted_lease(
        case
    )


def test_active_lease_is_not_redelivered_or_failed(
    tmp_path: Path,
) -> None:
    case = build_case(
        tmp_path,
        lease_expires_at="2026-08-08T12:01:30Z",
        delivery_attempt_count=3,
    )

    result = case["processor"].process_next()

    assert result is None
    assert case["store"].size() == 0

    assert case["lease_registry"].get(
        MISSION_ID
    ) == case["lease"]

    record = case["mission_registry"].get(
        MISSION_ID
    )

    assert record is not None
    assert record.status == (
        ExecutionMissionStatus.DELIVERED
    )


def test_expired_orphan_lease_is_released_without_error(
    tmp_path: Path,
) -> None:
    case = build_case(
        tmp_path,
        lease_expires_at="2026-08-08T12:00:30Z",
        delivery_attempt_count=1,
        include_mission=False,
    )

    result = case["processor"].process_next()

    assert result is None
    assert case["store"].size() == 0

    assert case["lease_registry"].get(
        MISSION_ID
    ) is None

    assert_no_persisted_lease(
        case
    )