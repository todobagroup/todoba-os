"""
TODOBA Pending Activation Scheduler

Provides the heartbeat that repeatedly asks
PendingActivationRuntime to process pending orders.

The scheduler owns timing only.
It does not own activation logic.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from backend.trading.pending.pending_activation_runtime import (
    PendingActivationRuntime,
)


@dataclass(frozen=True)
class PendingActivationSchedulerCycle:
    """
    Result of one pending activation cycle.
    """

    cycle_number: int
    activated_count: int


class PendingActivationScheduler:
    """
    Repeatedly run PendingActivationRuntime at a fixed interval.
    """

    def __init__(
        self,
        *,
        runtime: PendingActivationRuntime,
        interval_seconds: float = 5.0,
    ):
        if not isinstance(
            runtime,
            PendingActivationRuntime,
        ):
            raise TypeError(
                "PendingActivationScheduler requires "
                "PendingActivationRuntime."
            )

        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds must be greater than zero."
            )

        self.runtime = runtime
        self.interval_seconds = float(
            interval_seconds
        )

        self._task: Optional[
            asyncio.Task
        ] = None

        self._stop_event = asyncio.Event()

        self._cycle_count = 0
        self._last_cycle: Optional[
            PendingActivationSchedulerCycle
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
    ) -> Optional[PendingActivationSchedulerCycle]:
        return self._last_cycle

    @property
    def last_error(
        self,
    ) -> Optional[Exception]:
        return self._last_error

    async def start(self) -> bool:
        if self.running:
            return True

        self._stop_event = asyncio.Event()
        self._last_error = None

        self._task = asyncio.create_task(
            self._run(),
            name="todoba-pending-activation-scheduler",
        )

        return True

    async def stop(self) -> bool:
        if self._task is None:
            return True

        self._stop_event.set()

        await self._task

        self._task = None

        return True

    def run_cycle(
        self,
    ) -> PendingActivationSchedulerCycle:
        activated_count = self.runtime.process()

        self._cycle_count += 1

        cycle = PendingActivationSchedulerCycle(
            cycle_number=self._cycle_count,
            activated_count=activated_count,
        )

        self._last_cycle = cycle

        return cycle

    async def _run(self) -> None:
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