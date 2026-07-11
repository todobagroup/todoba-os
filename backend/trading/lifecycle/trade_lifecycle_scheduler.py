"""
TODOBA Trade Lifecycle Scheduler

Provides the heartbeat that repeatedly asks
TradeLifecycleMonitor to inspect registered trades.

Architecture:

TradeLifecycleScheduler
        ↓
TradeLifecycleMonitor.check_all()
        ↓
OpenTradeRegistry
        ↓
MT5 position and history evidence
        ↓
Trade Reflection
        ↓
Brain Memory

The scheduler owns timing only.
It does not own trade monitoring logic.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from backend.trading.lifecycle.trade_lifecycle_monitor import (
    TradeLifecycleMonitor,
    TradeLifecycleMonitorResult,
)


@dataclass(frozen=True)
class TradeLifecycleSchedulerCycle:
    """
    Result of one scheduler monitoring cycle.
    """

    cycle_number: int
    results: tuple[
        TradeLifecycleMonitorResult,
        ...
    ]


class TradeLifecycleScheduler:
    """
    Repeatedly run TradeLifecycleMonitor at a fixed interval.

    The scheduler is designed for an asyncio runtime such as
    TODOBA's Telegram Listener.
    """

    def __init__(
        self,
        *,
        monitor: TradeLifecycleMonitor,
        interval_seconds: float = 5.0,
    ):
        if not isinstance(
            monitor,
            TradeLifecycleMonitor,
        ):
            raise TypeError(
                "TradeLifecycleScheduler requires "
                "TradeLifecycleMonitor."
            )

        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds must be greater than zero."
            )

        self.monitor = monitor
        self.interval_seconds = float(
            interval_seconds
        )

        self._task: Optional[
            asyncio.Task
        ] = None

        self._stop_event = asyncio.Event()

        self._cycle_count = 0
        self._last_cycle: Optional[
            TradeLifecycleSchedulerCycle
        ] = None

        self._last_error: Optional[
            Exception
        ] = None

    @property
    def running(self) -> bool:
        """
        Return True while the scheduler task is active.
        """

        return (
            self._task is not None
            and not self._task.done()
        )

    @property
    def cycle_count(self) -> int:
        """
        Return the number of completed monitoring cycles.
        """

        return self._cycle_count

    @property
    def last_cycle(
        self,
    ) -> Optional[TradeLifecycleSchedulerCycle]:
        """
        Return the most recently completed cycle.
        """

        return self._last_cycle

    @property
    def last_error(
        self,
    ) -> Optional[Exception]:
        """
        Return the latest unexpected scheduler error.
        """

        return self._last_error

    async def start(self) -> bool:
        """
        Start the scheduler.

        Calling start more than once does not create
        duplicate heartbeat tasks.
        """

        if self.running:
            return True

        self._stop_event = asyncio.Event()
        self._last_error = None

        self._task = asyncio.create_task(
            self._run(),
            name="todoba-trade-lifecycle-scheduler",
        )

        return True

    async def stop(self) -> bool:
        """
        Stop the scheduler and wait for a clean shutdown.
        """

        if self._task is None:
            return True

        self._stop_event.set()

        await self._task

        self._task = None

        return True

    def run_cycle(
        self,
    ) -> TradeLifecycleSchedulerCycle:
        """
        Run one monitoring cycle immediately.

        This method is also useful for controlled tests and
        manual operational checks.
        """

        results = tuple(
            self.monitor.check_all()
        )

        self._cycle_count += 1

        cycle = TradeLifecycleSchedulerCycle(
            cycle_number=self._cycle_count,
            results=results,
        )

        self._last_cycle = cycle

        return cycle

    async def _run(self) -> None:
        """
        Internal scheduler heartbeat loop.
        """

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