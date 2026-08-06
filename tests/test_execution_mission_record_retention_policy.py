from datetime import datetime
from datetime import timezone

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_record_retention_policy import (
    ExecutionMissionRecordRetentionPolicy,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


def build_record(
    mission_id: str,
    status: ExecutionMissionStatus,
    completed_at: str | None = None,
    failed_at: str | None = None,
) -> ExecutionMissionRecord:
    mission = ExecutionMission(
        mission_id=mission_id,
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Retention Policy",
        created_at="2026-08-01T00:00:00Z",
        expires_at="2026-08-01T01:00:00Z",
        sequence=1,
    )

    return ExecutionMissionRecord(
        mission=mission,
        status=status,
        completed_at=completed_at,
        failed_at=failed_at,
    )


def test_policy_selects_expired_terminal_records() -> None:
    registry = ExecutionMissionRegistry()

    registry.register(
        build_record(
            mission_id="completed-expired",
            status=ExecutionMissionStatus.COMPLETED,
            completed_at="2026-07-01T00:00:00Z",
        )
    )

    registry.register(
        build_record(
            mission_id="failed-expired",
            status=ExecutionMissionStatus.FAILED,
            failed_at="2026-07-02T00:00:00Z",
        )
    )

    policy = ExecutionMissionRecordRetentionPolicy(
        retention_days=30
    )

    selected = policy.select(
        registry=registry,
        current_time=datetime(
            2026,
            8,
            6,
            tzinfo=timezone.utc,
        ),
    )

    assert selected == [
        "completed-expired",
        "failed-expired",
    ]


def test_policy_keeps_recent_terminal_records() -> None:
    registry = ExecutionMissionRegistry()

    registry.register(
        build_record(
            mission_id="completed-recent",
            status=ExecutionMissionStatus.COMPLETED,
            completed_at="2026-08-01T00:00:00Z",
        )
    )

    registry.register(
        build_record(
            mission_id="failed-recent",
            status=ExecutionMissionStatus.FAILED,
            failed_at="2026-08-02T00:00:00Z",
        )
    )

    policy = ExecutionMissionRecordRetentionPolicy(
        retention_days=30
    )

    selected = policy.select(
        registry=registry,
        current_time=datetime(
            2026,
            8,
            6,
            tzinfo=timezone.utc,
        ),
    )

    assert selected == []


def test_policy_ignores_active_records() -> None:
    registry = ExecutionMissionRegistry()

    registry.register(
        build_record(
            mission_id="active-created",
            status=ExecutionMissionStatus.CREATED,
        )
    )

    registry.register(
        build_record(
            mission_id="active-executing",
            status=ExecutionMissionStatus.EXECUTING,
        )
    )

    policy = ExecutionMissionRecordRetentionPolicy(
        retention_days=0
    )

    selected = policy.select(
        registry=registry,
        current_time=datetime(
            2026,
            8,
            6,
            tzinfo=timezone.utc,
        ),
    )

    assert selected == []


def test_policy_accepts_naive_iso_timestamp_as_utc() -> None:
    registry = ExecutionMissionRegistry()

    registry.register(
        build_record(
            mission_id="completed-naive",
            status=ExecutionMissionStatus.COMPLETED,
            completed_at="2026-07-01T00:00:00",
        )
    )

    policy = ExecutionMissionRecordRetentionPolicy(
        retention_days=30
    )

    selected = policy.select(
        registry=registry,
        current_time=datetime(
            2026,
            8,
            6,
            tzinfo=timezone.utc,
        ),
    )

    assert selected == [
        "completed-naive",
    ]