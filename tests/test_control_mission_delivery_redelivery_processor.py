from datetime import datetime
from datetime import timezone
from pathlib import Path

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_delivery_bridge import (
    ControlMissionDeliveryBridge,
)
from backend.trading.control.control_mission_delivery_lease import (
    ControlMissionDeliveryLease,
)
from backend.trading.control.control_mission_delivery_lease_persistence import (
    ControlMissionDeliveryLeasePersistence,
)
from backend.trading.control.control_mission_delivery_lease_registry import (
    ControlMissionDeliveryLeaseRegistry,
)
from backend.trading.control.control_mission_delivery_redelivery_processor import (
    ControlMissionDeliveryRedeliveryProcessor,
)
from backend.trading.control.control_mission_lifecycle_service import (
    ControlMissionLifecycleService,
)
from backend.trading.control.control_mission_record import (
    ControlMissionRecord,
)
from backend.trading.control.control_mission_registry import (
    ControlMissionRegistry,
)
from backend.trading.control.control_mission_repository import (
    ControlMissionRepository,
)
from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
)
from backend.trading.control.control_mission_store import (
    ControlMissionStore,
)


MISSION_ID = "control-redelivery-001"
AGENT_ID = "trusted-agent-001"


def fixed_clock() -> datetime:
    return datetime(
        2026,
        8,
        15,
        12,
        1,
        0,
        tzinfo=timezone.utc,
    )


def build_mission() -> ControlMission:
    return ControlMission(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        account_fingerprint="demo-account",
        action=ControlAction.CLOSE_GREEN,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=5414928751,
        created_at="2026-08-15T12:00:00Z",
        expires_at="2026-08-15T13:00:00Z",
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

    repository = ControlMissionRepository()
    store = ControlMissionStore()

    if include_mission:
        repository.save(
            mission
        )

        store.push(
            mission
        )

        assert store.pop() == mission

    lease_registry = (
        ControlMissionDeliveryLeaseRegistry()
    )

    lease = ControlMissionDeliveryLease(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        leased_at="2026-08-15T12:00:00Z",
        expires_at=lease_expires_at,
    )

    lease_registry.acquire(
        lease
    )

    lease_persistence = (
        ControlMissionDeliveryLeasePersistence(
            tmp_path
            / "control_delivery_leases.json"
        )
    )

    lease_persistence.save(
        lease_registry
    )

    mission_registry = ControlMissionRegistry()

    mission_registry.register(
        ControlMissionRecord(
            mission=mission,
            status=ControlMissionStatus.DELIVERED,
            delivered_at="2026-08-15T12:00:00Z",
            delivery_attempt_count=(
                delivery_attempt_count
            ),
        )
    )

    lifecycle_service = (
        ControlMissionLifecycleService(
            mission_registry
        )
    )

    processor = (
        ControlMissionDeliveryRedeliveryProcessor(
            repository=repository,
            delivery_bridge=(
                ControlMissionDeliveryBridge(
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
        ControlMissionDeliveryLeaseRegistry()
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
        lease_expires_at="2026-08-15T12:00:30Z",
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
    assert record.status is (
        ControlMissionStatus.DELIVERED
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
        lease_expires_at="2026-08-15T12:00:30Z",
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
    assert record.status is (
        ControlMissionStatus.FAILED
    )
    assert record.failed_at == (
        "2026-08-15T12:01:00Z"
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
        lease_expires_at="2026-08-15T12:01:30Z",
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
    assert record.status is (
        ControlMissionStatus.DELIVERED
    )


def test_expired_orphan_lease_is_released_without_error(
    tmp_path: Path,
) -> None:
    case = build_case(
        tmp_path,
        lease_expires_at="2026-08-15T12:00:30Z",
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