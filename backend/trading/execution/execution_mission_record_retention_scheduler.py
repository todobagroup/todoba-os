"""
TODOBA Execution Mission Record Retention Scheduler

Provides the heartbeat that periodically evaluates
execution mission records for retention cleanup.

Architecture:

ExecutionMissionRecordRetentionScheduler
↓
ExecutionMissionRecordRetentionPolicy
↓
ExecutionMissionRecordCleanup
↓
ExecutionMissionRegistry

The scheduler owns timing only.
It does not own retention policy or cleanup logic.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Callable
from typing import Optional

from backend.trading.execution.execution_mission_record_cleanup import (
    ExecutionMissionRecordCleanup,
)
from backend.trading.execution.execution_mission_record_retention_policy import (
    ExecutionMissionRecordRetentionPolicy,
)


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


@dataclass(frozen=True)
class ExecutionMissionRecordRetentionSchedulerCycle:
    """
    Result of one retention scheduler cycle.
    """

    cycle_number: int
    selected_count: int
    removed_count: int


class ExecutionMissionRecordRetentionScheduler:
    """
    Periodically evaluate and clean retained
    execution mission records.
    """

    def __init__(
        self,
        *,
        policy: ExecutionMissionRecordRetentionPolicy,
        cleanup: ExecutionMissionRecordCleanup,
        interval_seconds: float = 3600.0,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not isinstance(
            policy,
            ExecutionMissionRecordRetentionPolicy,
        ):
            raise TypeError(
                "ExecutionMissionRecordRetentionScheduler "
                "requires "
                "ExecutionMissionRecordRetentionPolicy."
            )

        if not isinstance(
            cleanup,
            ExecutionMissionRecordCleanup,
        ):
            raise TypeError(
                "ExecutionMissionRecordRetentionScheduler "
                "requires ExecutionMissionRecordCleanup."
            )

        if not isinstance(
            interval_seconds,
            (int, float),
        ):
            raise TypeError(
                "interval_seconds must be numeric."
            )

        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds must be greater than zero."
            )

        if not callable(
            clock
        ):
            raise TypeError(
                "clock must be callable."
            )

        self.policy = policy
        self.cleanup = cleanup
        self.interval_seconds = float(
            interval_seconds
        )
        self.clock = clock

        self._task: Optional[
            asyncio.Task
        ] = None

        self._stop_event = asyncio.Event()

        self._cycle_count = 0

        self._last_cycle: Optional[
            ExecutionMissionRecordRetentionSchedulerCycle
        ] = None

        self._last_error: Optional[
            Exception
        ] = None

    @property
    def running(
        self,
    ) -> bool:
        return (
            self._task is not None
            and not self._task.done()
        )

    @property
    def cycle_count(
        self,
    ) -> int:
        return self._cycle_count

    @property
    def last_cycle(
        self,
    ) -> Optional[
        ExecutionMissionRecordRetentionSchedulerCycle
    ]:
        return self._last_cycle

    @property
    def last_error(
        self,
    ) -> Optional[Exception]:
        return self._last_error

    async def start(
        self,
    ) -> bool:
        if self.running:
            return True

        self._stop_event = asyncio.Event()
        self._last_error = None

        self._task = asyncio.create_task(
            self._run(),
            name=(
                "todoba-execution-mission-"
                "record-retention-scheduler"
            ),
        )

        return True

    async def stop(
        self,
    ) -> bool:
        if self._task is None:
            return True

        self._stop_event.set()

        await self._task

        self._task = None

        return True

    def run_cycle(
        self,
    ) -> ExecutionMissionRecordRetentionSchedulerCycle:
        current_time = self.clock()

        if not isinstance(
            current_time,
            datetime,
        ):
            raise TypeError(
                "clock must return datetime."
            )

        mission_ids = self.policy.select(
            self.cleanup.registry,
            current_time,
        )

        removed_count = self.cleanup.cleanup(
            mission_ids
        )

        self._cycle_count += 1

        cycle = (
            ExecutionMissionRecordRetentionSchedulerCycle(
                cycle_number=self._cycle_count,
                selected_count=len(
                    mission_ids
                ),
                removed_count=removed_count,
            )
        )

        self._last_cycle = cycle

        return cycle

    async def _run(
        self,
    ) -> None:
        try:
            while not self._stop_event.is_set():
                self.run_cycle()

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.interval_seconds,
                    )

                except asyncio.TimeoutError:
                    continue

        except asyncio.CancelledError:
            raise

        except Exception as error:
            self._last_error = error
            self._stop_event.set()