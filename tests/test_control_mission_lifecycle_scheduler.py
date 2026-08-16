import asyncio

import pytest

from backend.trading.control.control_mission_delivery_redelivery_processor import (
    ControlMissionDeliveryRedeliveryProcessor,
)
from backend.trading.control.control_mission_lifecycle_scheduler import (
    ControlMissionLifecycleScheduler,
)
from backend.trading.control.control_mission_lifecycle_scheduler import (
    ControlMissionLifecycleSchedulerCycle,
)


class FakeRedeliveryProcessor(
    ControlMissionDeliveryRedeliveryProcessor
):
    def __init__(
        self,
        *,
        results=None,
        fail: bool = False,
    ) -> None:
        self.results = list(
            results or []
        )
        self.fail = fail
        self.process_count = 0

    def process_next(self):
        self.process_count += 1

        if self.fail:
            raise RuntimeError(
                "Processor cycle failed."
            )

        if not self.results:
            return None

        return self.results.pop(0)


def test_manual_cycle_calls_processor() -> None:
    processor = FakeRedeliveryProcessor(
        results=[
            object()
        ]
    )

    scheduler = ControlMissionLifecycleScheduler(
        processor=processor,
        interval_seconds=1.0,
    )

    cycle = scheduler.run_cycle()

    assert processor.process_count == 1
    assert scheduler.cycle_count == 1

    assert isinstance(
        cycle,
        ControlMissionLifecycleSchedulerCycle,
    )

    assert cycle.processed is True
    assert scheduler.last_cycle == cycle


def test_invalid_interval_is_rejected() -> None:
    processor = FakeRedeliveryProcessor()

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        ControlMissionLifecycleScheduler(
            processor=processor,
            interval_seconds=0,
        )


def test_invalid_processor_is_rejected() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "requires "
            "ControlMissionDeliveryRedeliveryProcessor"
        ),
    ):
        ControlMissionLifecycleScheduler(
            processor="not-a-processor",
            interval_seconds=1.0,
        )


@pytest.mark.anyio
async def test_scheduler_runs_repeated_cycles() -> None:
    processor = FakeRedeliveryProcessor()

    scheduler = ControlMissionLifecycleScheduler(
        processor=processor,
        interval_seconds=0.01,
    )

    assert await scheduler.start() is True

    await asyncio.sleep(
        0.045
    )

    assert await scheduler.stop() is True

    assert scheduler.running is False
    assert processor.process_count >= 2
    assert scheduler.cycle_count >= 2


@pytest.mark.anyio
async def test_start_does_not_create_duplicate_loop() -> None:
    processor = FakeRedeliveryProcessor()

    scheduler = ControlMissionLifecycleScheduler(
        processor=processor,
        interval_seconds=0.02,
    )

    assert await scheduler.start() is True

    first_task = scheduler._task

    assert await scheduler.start() is True
    assert scheduler._task is first_task

    await scheduler.stop()


@pytest.mark.anyio
async def test_stop_before_start_is_safe() -> None:
    processor = FakeRedeliveryProcessor()

    scheduler = ControlMissionLifecycleScheduler(
        processor=processor,
        interval_seconds=1.0,
    )

    assert await scheduler.stop() is True
    assert scheduler.running is False


@pytest.mark.anyio
async def test_scheduler_records_unexpected_error() -> None:
    processor = FakeRedeliveryProcessor(
        fail=True
    )

    scheduler = ControlMissionLifecycleScheduler(
        processor=processor,
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

    assert str(
        scheduler.last_error
    ) == "Processor cycle failed."

    await scheduler.stop()