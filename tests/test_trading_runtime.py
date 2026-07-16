"""
Tests for TODOBA TradingRuntime.

These tests do not connect to Telegram.
These tests do not connect to MT5.
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from backend.task.task import Task
from backend.task.task_status import TaskStatus
from backend.trading.intent.trading_intent import (
    TradingIntent,
)
from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)
from backend.trading.lifecycle.trade_status import (
    TradeStatus,
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


class DemoOpenTradePersistence:

    def __init__(self):
        self.persisted_trade = None

    def persist(
        self,
        trade_record,
    ):
        self.persisted_trade = trade_record


class DemoTimelineService:

    def __init__(self):
        self.started_trade_id = None

    def start_trade(
        self,
        trade_id,
    ):
        self.started_trade_id = trade_id


def create_trade_task() -> Task:
    intent = TradingIntent(
        order_type="BUY NOW",
        asset="XAUUSD",
        sl=4095.0,
        tp=4125.0,
    )

    return Task(
        task_type="trade",
        payload=intent,
        created_at=datetime.now(),
    )


def create_trade_record() -> TradeRecord:
    return TradeRecord(
        trade_id="trade-001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.05,
        status=TradeStatus.OPEN,
        order=1001,
        deal=2001,
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


def test_runtime_registers_open_trade():
    runtime = TradingRuntime(
        execution_pipeline=(
            DemoExecutionPipeline()
        )
    )

    persistence = DemoOpenTradePersistence()
    timeline = DemoTimelineService()

    runtime.open_trade_persistence = persistence
    runtime.timeline_service = timeline

    trade_record = create_trade_record()

    result = runtime.register_open_trade(
        trade_record
    )

    assert result is trade_record
    assert persistence.persisted_trade is trade_record
    assert timeline.started_trade_id == trade_record.trade_id


def test_register_open_trade_requires_trade_record():
    runtime = TradingRuntime(
        execution_pipeline=(
            DemoExecutionPipeline()
        )
    )

    with pytest.raises(
        TypeError,
        match="requires TradeRecord",
    ):
        runtime.register_open_trade(
            "not-a-trade-record"
        )