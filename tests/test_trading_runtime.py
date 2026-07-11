"""
Tests for TODOBA TradingRuntime.

These tests do not connect to Telegram.
These tests do not connect to MT5.
"""

from datetime import datetime

import pytest

from backend.task.task import Task
from backend.task.task_status import TaskStatus
from backend.trading.intent.trading_intent import (
    TradingIntent,
)
from backend.trading.runtime.trading_runtime import (
    TradingRuntime,
)


class DemoExecutionPipeline:
    """
    Safe execution substitute for TradingRuntime tests.
    """

    def __init__(self):
        self.execute_count = 0
        self.last_plan = None

    def execute(self, plan):
        self.execute_count += 1
        self.last_plan = plan

        return {
            "status": "DEMO_SUCCESS",
            "symbol": plan.symbol,
            "order_type": plan.order_type,
        }


def create_trade_task() -> Task:
    intent = TradingIntent(
        action="BUY",
        asset="XAUUSD",
        sl=4095.0,
        tp=4125.0,
    )

    return Task(
        task_type="trade",
        payload=intent,
        created_at=datetime.now(),
    )


def test_runtime_dispatches_trade_task():
    pipeline = DemoExecutionPipeline()

    runtime = TradingRuntime(
        execution_pipeline=pipeline
    )

    assert runtime.start() is True

    task = create_trade_task()

    result = runtime.dispatch(
        task
    )

    assert result["status"] == "DEMO_SUCCESS"
    assert result["symbol"] == "XAUUSD"
    assert result["order_type"] == "BUY NOW"

    assert pipeline.execute_count == 1
    assert task.status == TaskStatus.COMPLETED
    assert task.worker == "TradingWorker"

    assert runtime.stop() is True


def test_runtime_requires_start():
    runtime = TradingRuntime(
        execution_pipeline=(
            DemoExecutionPipeline()
        )
    )

    with pytest.raises(
        RuntimeError,
        match="not running",
    ):
        runtime.dispatch(
            create_trade_task()
        )


def test_start_is_idempotent():
    runtime = TradingRuntime(
        execution_pipeline=(
            DemoExecutionPipeline()
        )
    )

    assert runtime.start() is True
    assert runtime.start() is True
    assert runtime.running is True

    runtime.stop()


def test_stop_before_start_is_safe():
    runtime = TradingRuntime(
        execution_pipeline=(
            DemoExecutionPipeline()
        )
    )

    assert runtime.stop() is True
    assert runtime.running is False


def test_runtime_rejects_invalid_task():
    runtime = TradingRuntime(
        execution_pipeline=(
            DemoExecutionPipeline()
        )
    )

    runtime.start()

    with pytest.raises(
        TypeError,
        match="requires Task",
    ):
        runtime.dispatch(
            "not-a-task"
        )

    runtime.stop()


def test_runtime_rejects_non_trade_task():
    runtime = TradingRuntime(
        execution_pipeline=(
            DemoExecutionPipeline()
        )
    )

    runtime.start()

    task = Task(
        task_type="video",
        payload={
            "prompt": "Create video"
        },
        created_at=datetime.now(),
    )

    with pytest.raises(
        ValueError,
        match="only accepts trade tasks",
    ):
        runtime.dispatch(
            task
        )

    runtime.stop()


def test_runtime_requires_execution_pipeline():
    with pytest.raises(
        ValueError,
        match="requires an execution pipeline",
    ):
        TradingRuntime(
            execution_pipeline=None
        )