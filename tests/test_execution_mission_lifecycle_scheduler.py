from pathlib import Path
import sys
import asyncio

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from backend.trading.execution.execution_mission_acknowledgement_processor import (
    ExecutionMissionAcknowledgementProcessor,
)

from backend.trading.execution.execution_mission_lifecycle_scheduler import (
    ExecutionMissionLifecycleScheduler,
    ExecutionMissionLifecycleSchedulerCycle,
)


class FakeAcknowledgementProcessor(
    ExecutionMissionAcknowledgementProcessor
):

    def __init__(
        self,
        results=None,
        fail=False,
    ):
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



def test_manual_cycle_calls_processor():

    processor = FakeAcknowledgementProcessor(
        results=[
            object()
        ]
    )

    scheduler = ExecutionMissionLifecycleScheduler(
        processor=processor,
        interval_seconds=1.0,
    )

    cycle = scheduler.run_cycle()

    assert processor.process_count == 1

    assert scheduler.cycle_count == 1

    assert isinstance(
        cycle,
        ExecutionMissionLifecycleSchedulerCycle,
    )

    assert cycle.processed is True

    assert scheduler.last_cycle == cycle



def test_invalid_interval_is_rejected():

    processor = FakeAcknowledgementProcessor()

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        ExecutionMissionLifecycleScheduler(
            processor=processor,
            interval_seconds=0,
        )



def test_invalid_processor_is_rejected():

    with pytest.raises(
        TypeError,
        match="requires ExecutionMissionAcknowledgementProcessor",
    ):
        ExecutionMissionLifecycleScheduler(
            processor="not-a-processor",
            interval_seconds=1.0,
        )



@pytest.mark.anyio
async def test_scheduler_runs_repeated_cycles():

    processor = FakeAcknowledgementProcessor()

    scheduler = ExecutionMissionLifecycleScheduler(
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
async def test_start_does_not_create_duplicate_loop():

    processor = FakeAcknowledgementProcessor()

    scheduler = ExecutionMissionLifecycleScheduler(
        processor=processor,
        interval_seconds=0.02,
    )

    assert await scheduler.start() is True

    first_task = scheduler._task

    assert await scheduler.start() is True

    assert scheduler._task is first_task

    await scheduler.stop()



@pytest.mark.anyio
async def test_stop_before_start_is_safe():

    processor = FakeAcknowledgementProcessor()

    scheduler = ExecutionMissionLifecycleScheduler(
        processor=processor,
        interval_seconds=1.0,
    )

    assert await scheduler.stop() is True

    assert scheduler.running is False



@pytest.mark.anyio
async def test_scheduler_records_unexpected_error():

    processor = FakeAcknowledgementProcessor(
        fail=True
    )

    scheduler = ExecutionMissionLifecycleScheduler(
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

    assert (
        str(scheduler.last_error)
        == "Processor cycle failed."
    )

    await scheduler.stop()