"""
Tests for TODOBA TradeLifecycleScheduler.

These tests do not connect to Telegram.
These tests do not connect to MT5.
"""

import asyncio

import pytest

from backend.trading.lifecycle.open_trade_registry import (
    OpenTradeRegistry,
)
from backend.trading.lifecycle.trade_lifecycle_monitor import (
    TradeLifecycleMonitor,
    TradeLifecycleMonitorResult,
)
from backend.trading.lifecycle.trade_lifecycle_scheduler import (
    TradeLifecycleScheduler,
)


class FakeLifecycleMonitor(
    TradeLifecycleMonitor
):
    """
    Safe monitor substitute that satisfies the existing
    TradeLifecycleMonitor contract.
    """

    def __init__(
        self,
        results=None,
        fail=False,
    ):
        self.registry = OpenTradeRegistry()
        self.results = list(
            results or []
        )
        self.fail = fail
        self.check_count = 0

    def check_all(self):
        self.check_count += 1

        if self.fail:
            raise RuntimeError(
                "Monitor cycle failed."
            )

        return list(
            self.results
        )


def create_open_result():
    return TradeLifecycleMonitorResult(
        status="open",
        trade_id="TRD-000001",
        position_id=90001,
    )


def test_manual_cycle_calls_monitor():
    monitor = FakeLifecycleMonitor(
        results=[
            create_open_result()
        ]
    )

    scheduler = TradeLifecycleScheduler(
        monitor=monitor,
        interval_seconds=1.0,
    )

    cycle = scheduler.run_cycle()

    assert monitor.check_count == 1
    assert scheduler.cycle_count == 1
    assert cycle.cycle_number == 1
    assert len(cycle.results) == 1
    assert cycle.results[0].status == "open"
    assert scheduler.last_cycle == cycle


def test_invalid_interval_is_rejected():
    monitor = FakeLifecycleMonitor()

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        TradeLifecycleScheduler(
            monitor=monitor,
            interval_seconds=0,
        )


def test_invalid_monitor_is_rejected():
    with pytest.raises(
        TypeError,
        match="requires TradeLifecycleMonitor",
    ):
        TradeLifecycleScheduler(
            monitor="not-a-monitor",
            interval_seconds=1.0,
        )


@pytest.mark.anyio
async def test_scheduler_runs_repeated_cycles():
    monitor = FakeLifecycleMonitor()

    scheduler = TradeLifecycleScheduler(
        monitor=monitor,
        interval_seconds=0.01,
    )

    assert await scheduler.start() is True

    await asyncio.sleep(
        0.045
    )

    assert await scheduler.stop() is True

    assert scheduler.running is False
    assert monitor.check_count >= 2
    assert scheduler.cycle_count >= 2


@pytest.mark.anyio
async def test_start_does_not_create_duplicate_loop():
    monitor = FakeLifecycleMonitor()

    scheduler = TradeLifecycleScheduler(
        monitor=monitor,
        interval_seconds=0.02,
    )

    assert await scheduler.start() is True

    first_task = scheduler._task

    assert await scheduler.start() is True

    assert scheduler._task is first_task

    await scheduler.stop()


@pytest.mark.anyio
async def test_stop_before_start_is_safe():
    monitor = FakeLifecycleMonitor()

    scheduler = TradeLifecycleScheduler(
        monitor=monitor,
        interval_seconds=1.0,
    )

    assert await scheduler.stop() is True
    assert scheduler.running is False


@pytest.mark.anyio
async def test_scheduler_records_unexpected_error():
    monitor = FakeLifecycleMonitor(
        fail=True
    )

    scheduler = TradeLifecycleScheduler(
        monitor=monitor,
        interval_seconds=0.01,
    )

    await scheduler.start()

    await asyncio.sleep(
        0.02
    )

    assert scheduler.running is False

    assert isinstance(
        scheduler.last_error,
        RuntimeError,
    )

    assert (
        str(scheduler.last_error)
        == "Monitor cycle failed."
    )

    await scheduler.stop()