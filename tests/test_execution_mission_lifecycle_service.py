import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.execution_mission import (
    ExecutionMission,
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


def build_record() -> ExecutionMissionRecord:
    mission = ExecutionMission(
        mission_id="lifecycle-001",
        agent_id="trusted-agent-001",
        account_fingerprint="account-test",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4090.0,
        tp=4120.0,
        magic_number=10001,
        comment="TODOBA",
        created_at="2026-07-29T00:00:00",
        expires_at="2026-07-29T01:00:00",
        sequence=1,
    )

    return ExecutionMissionRecord(
        mission=mission
    )


def test_lifecycle_service_marks_mission_delivered() -> None:
    record = build_record()

    registry = ExecutionMissionRegistry()

    registry.register(
        record
    )

    service = ExecutionMissionLifecycleService(
        registry
    )

    updated_record = service.mark_delivered(
        mission_id="lifecycle-001",
        delivered_at="2026-07-29T00:04:00",
    )

    assert updated_record.status == (
        ExecutionMissionStatus.DELIVERED
    )

    assert updated_record.delivered_at == (
        "2026-07-29T00:04:00"
    )

    assert updated_record.delivery_attempt_count == 1


def test_lifecycle_service_increments_delivery_attempt_count() -> None:
    record = build_record()

    registry = ExecutionMissionRegistry()

    registry.register(
        record
    )

    service = ExecutionMissionLifecycleService(
        registry
    )

    service.mark_delivered(
        mission_id="lifecycle-001",
        delivered_at="2026-07-29T00:04:00",
    )

    updated_record = service.mark_delivered(
        mission_id="lifecycle-001",
        delivered_at="2026-07-29T00:06:00",
    )

    assert updated_record.delivery_attempt_count == 2

    assert updated_record.delivered_at == (
        "2026-07-29T00:06:00"
    )


def test_lifecycle_service_acknowledges_mission() -> None:
    record = build_record()

    registry = ExecutionMissionRegistry()

    registry.register(
        record
    )

    service = ExecutionMissionLifecycleService(
        registry
    )

    updated_record = service.acknowledge(
        mission_id="lifecycle-001",
        acknowledged_at="2026-07-29T00:05:00",
    )

    assert updated_record.status == (
        ExecutionMissionStatus.ACKNOWLEDGED
    )

    assert updated_record.acknowledged_at == (
        "2026-07-29T00:05:00"
    )