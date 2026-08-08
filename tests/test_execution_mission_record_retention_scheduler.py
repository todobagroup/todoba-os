import asyncio
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_record_cleanup import (
    ExecutionMissionRecordCleanup,
)
from backend.trading.execution.execution_mission_record_persistence import (
    ExecutionMissionRecordPersistence,
)
from backend.trading.execution.execution_mission_record_retention_policy import (
    ExecutionMissionRecordRetentionPolicy,
)
from backend.trading.execution.execution_mission_record_retention_scheduler import (
    ExecutionMissionRecordRetentionScheduler,
    ExecutionMissionRecordRetentionSchedulerCycle,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


def fixed_clock() -> datetime:
    return datetime(
        2026,
        8,
        8,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )


def build_record(
    *,
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
        comment="TODOBA Proof077 Retention",
        created_at="2026-07-01T00:00:00Z",
        expires_at="2026-07-01T01:00:00Z",
        sequence=1,
    )

    return ExecutionMissionRecord(
        mission=mission,
        status=status,
        completed_at=completed_at,
        failed_at=failed_at,
    )


def build_scheduler(
    tmp_path: Path,
) -> tuple[
    ExecutionMissionRecordRetentionScheduler,
    ExecutionMissionRegistry,
]:
    registry = ExecutionMissionRegistry()

    persistence = ExecutionMissionRecordPersistence(
        tmp_path / "records.json"
    )

    cleanup = ExecutionMissionRecordCleanup(
        registry,
        persistence,
    )

    policy = ExecutionMissionRecordRetentionPolicy(
        retention_days=30
    )

    scheduler = ExecutionMissionRecordRetentionScheduler(
        policy=policy,
        cleanup=cleanup,
        interval_seconds=1.0,
        clock=fixed_clock,
    )

    return scheduler, registry


def test_cycle_removes_expired_terminal_records(
    tmp_path: Path,
) -> None:
    scheduler, registry = build_scheduler(
        tmp_path
    )

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
            failed_at="2026-07-01T00:00:00Z",
        )
    )

    registry.register(
        build_record(
            mission_id="failed-recent",
            status=ExecutionMissionStatus.FAILED,
            failed_at="2026-08-02T00:00:00Z",
        )
    )

    cycle = scheduler.run_cycle()

    assert isinstance(
        cycle,
        ExecutionMissionRecordRetentionSchedulerCycle,
    )

    assert cycle.cycle_number == 1
    assert cycle.selected_count == 2
    assert cycle.removed_count == 2

    assert registry.get(
        "completed-expired"
    ) is None

    assert registry.get(
        "failed-expired"
    ) is None

    assert registry.get(
        "failed-recent"
    ) is not None


def test_cycle_keeps_non_terminal_records(
    tmp_path: Path,
) -> None:
    scheduler, registry = build_scheduler(
        tmp_path
    )

    registry.register(
        build_record(
            mission_id="delivered-active",
            status=ExecutionMissionStatus.DELIVERED,
        )
    )

    cycle = scheduler.run_cycle()

    assert cycle.selected_count == 0
    assert cycle.removed_count == 0

    assert registry.get(
        "delivered-active"
    ) is not None


def test_invalid_interval_is_rejected(
    tmp_path: Path,
) -> None:
    registry = ExecutionMissionRegistry()

    persistence = ExecutionMissionRecordPersistence(
        tmp_path / "records.json"
    )

    cleanup = ExecutionMissionRecordCleanup(
        registry,
        persistence,
    )

    policy = ExecutionMissionRecordRetentionPolicy(
        retention_days=30
    )

    with pytest.raises(
        ValueError,
        match="interval_seconds must be greater than zero.",
    ):
        ExecutionMissionRecordRetentionScheduler(
            policy=policy,
            cleanup=cleanup,
            interval_seconds=0,
        )


@pytest.mark.anyio
async def test_scheduler_runs_repeated_cycles(
    tmp_path: Path,
) -> None:
    scheduler, _ = build_scheduler(
        tmp_path
    )

    scheduler.interval_seconds = 0.01

    assert await scheduler.start() is True

    await asyncio.sleep(
        0.035
    )

    assert await scheduler.stop() is True

    assert scheduler.running is False
    assert scheduler.cycle_count >= 2


@pytest.mark.anyio
async def test_start_does_not_create_duplicate_loop(
    tmp_path: Path,
) -> None:
    scheduler, _ = build_scheduler(
        tmp_path
    )

    scheduler.interval_seconds = 0.02

    assert await scheduler.start() is True

    first_task = scheduler._task

    assert await scheduler.start() is True

    assert scheduler._task is first_task

    await scheduler.stop()