"""
TODOBA Execution Mission Lifecycle Scheduler

Provides the heartbeat that repeatedly asks
Execution Mission evidence processors to consume
Trusted Agent evidence.

Architecture:

ExecutionMissionLifecycleScheduler
        ↓
ExecutionMissionEvidenceProcessors
        ↓
ExecutionMissionLifecycleService
        ↓
ExecutionMissionRegistry

The scheduler owns timing only.
It does not own mission lifecycle logic.
"""


import asyncio
from dataclasses import dataclass
from typing import Optional

from backend.trading.execution.execution_mission_acknowledgement_processor import (
    ExecutionMissionAcknowledgementProcessor,
)


@dataclass(frozen=True)
class ExecutionMissionLifecycleSchedulerCycle:
    """
    Result of one scheduler processing cycle.
    """

    cycle_number: int
    processed: bool


class ExecutionMissionLifecycleScheduler:
    """
    Repeatedly run execution mission evidence processing
    at a fixed interval.

    Backward compatible:
    - accepts one processor
    - accepts multiple processors
    """

    def __init__(
        self,
        *,
        processor: Optional[
            ExecutionMissionAcknowledgementProcessor
        ] = None,
        processors: Optional[
            list
        ] = None,
        interval_seconds: float = 5.0,
    ):

        if processor is None and not processors:
            raise TypeError(
                "ExecutionMissionLifecycleScheduler "
                "requires processor or processors."
            )

        if processor is not None:
            if not isinstance(
                processor,
                ExecutionMissionAcknowledgementProcessor,
            ):
                raise TypeError(
                    "ExecutionMissionLifecycleScheduler "
                    "requires ExecutionMissionAcknowledgementProcessor."
                )

            self.processors = [
                processor
            ]

        else:
            self.processors = list(
                processors
            )

        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds must be greater than zero."
            )

        self.interval_seconds = float(
            interval_seconds
        )

        self._task: Optional[
            asyncio.Task
        ] = None

        self._stop_event = asyncio.Event()

        self._cycle_count = 0

        self._last_cycle: Optional[
            ExecutionMissionLifecycleSchedulerCycle
        ] = None

        self._last_error: Optional[
            Exception
        ] = None

    @property
    def running(self) -> bool:
        return (
            self._task is not None
            and not self._task.done()
        )

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def last_cycle(
        self,
    ) -> Optional[
        ExecutionMissionLifecycleSchedulerCycle
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
                "lifecycle-scheduler"
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
    ) -> ExecutionMissionLifecycleSchedulerCycle:

        processed = False

        for processor in self.processors:

            result = processor.process_next()

            if result is not None:
                processed = True

        self._cycle_count += 1

        cycle = (
            ExecutionMissionLifecycleSchedulerCycle(
                cycle_number=self._cycle_count,
                processed=processed,
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