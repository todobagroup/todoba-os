"""
TODOBA Control Mission Lifecycle Scheduler

Provides the heartbeat that repeatedly asks the
Control Mission redelivery processor to inspect
expired delivery leases.

Architecture:

ControlMissionLifecycleScheduler
        ->
ControlMissionDeliveryRedeliveryProcessor
        ->
ControlMissionLifecycleService

The scheduler owns timing only.
It does not own control mission lifecycle logic.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from backend.trading.control.control_mission_delivery_redelivery_processor import (
    ControlMissionDeliveryRedeliveryProcessor,
)


@dataclass(frozen=True)
class ControlMissionLifecycleSchedulerCycle:
    """
    Result of one scheduler processing cycle.
    """

    cycle_number: int
    processed: bool


class ControlMissionLifecycleScheduler:
    """
    Repeatedly run control mission redelivery
    processing at a fixed interval.
    """

    def __init__(
        self,
        *,
        processor: ControlMissionDeliveryRedeliveryProcessor,
        interval_seconds: float = 5.0,
    ) -> None:
        if not isinstance(
            processor,
            ControlMissionDeliveryRedeliveryProcessor,
        ):
            raise TypeError(
                "ControlMissionLifecycleScheduler "
                "requires "
                "ControlMissionDeliveryRedeliveryProcessor."
            )

        if (
            not isinstance(
                interval_seconds,
                (int, float),
            )
            or isinstance(
                interval_seconds,
                bool,
            )
            or interval_seconds <= 0
        ):
            raise ValueError(
                "interval_seconds must be "
                "greater than zero."
            )

        self.processor = processor
        self.interval_seconds = float(
            interval_seconds
        )

        self._task: Optional[
            asyncio.Task
        ] = None

        self._stop_event = asyncio.Event()

        self._cycle_count = 0

        self._last_cycle: Optional[
            ControlMissionLifecycleSchedulerCycle
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
        ControlMissionLifecycleSchedulerCycle
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
                "todoba-control-mission-"
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
    ) -> ControlMissionLifecycleSchedulerCycle:
        result = self.processor.process_next()

        self._cycle_count += 1

        cycle = ControlMissionLifecycleSchedulerCycle(
            cycle_number=self._cycle_count,
            processed=result is not None,
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