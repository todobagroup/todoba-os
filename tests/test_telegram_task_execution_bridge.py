"""
Tests for TODOBA TelegramTaskExecutionBridge.

These tests do not connect to Telegram.
These tests do not connect to MT5.
These tests do not send live orders.
"""

from datetime import datetime, timezone

import pytest

from backend.integrations.telegram_task_execution_bridge import (
    TelegramTaskExecutionBridge,
)
from backend.integrations.telegram_task_producer import (
    TelegramTaskProducer,
)
from backend.task.task_status import TaskStatus
from backend.trading.profile.trading_profile import (
    TradingProfile,
)
from backend.trading.runtime.trading_runtime import (
    TradingRuntime,
)
from backend.trading.signal.incoming_signal import (
    IncomingSignal,
)


class DemoExecutionPipeline:
    """
    Safe test substitute for LiveExecutionPipeline.
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
            "sl": plan.sl,
            "tp": plan.tp,
        }


def create_profile(
    *,
    max_open_trades: int = 3,
) -> TradingProfile:
    return TradingProfile(
        profile_name="telegram_bridge_test",
        risk_percent=1.0,
        max_open_trades=max_open_trades,
        allowed_symbols=("XAUUSD",),
        lot_policy_name="FIXED_001",
    )


def create_signal() -> IncomingSignal:
    return IncomingSignal(
        source="telegram",
        message=(
            "BUY GOLD NOW\n"
            "SL 4095\n"
            "TP 4125"
        ),
        received_at=datetime.now(
            timezone.utc
        ),
        sender="demo_channel",
        sender_id=101,
        chat_id=-100123,
        message_id=500,
    )


def create_bridge(
    *,
    max_open_trades: int = 3,
):
    execution_pipeline = (
        DemoExecutionPipeline()
    )

    runtime = TradingRuntime(
        execution_pipeline=execution_pipeline
    )

    producer = TelegramTaskProducer(
        create_profile(
            max_open_trades=(
                max_open_trades
            )
        )
    )

    bridge = TelegramTaskExecutionBridge(
        producer=producer,
        runtime=runtime,
    )

    return (
        bridge,
        runtime,
        execution_pipeline,
    )


def test_approved_signal_runs_through_runtime():
    bridge, runtime, execution_pipeline = (
        create_bridge()
    )

    assert runtime.start() is True

    result = bridge.execute(
        create_signal(),
        open_position_count=0,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    assert result.status == "executed"
    assert result.task is not None
    assert (
        result.task.status
        == TaskStatus.COMPLETED
    )
    assert (
        result.task.worker
        == "TradingWorker"
    )
    assert (
        execution_pipeline.execute_count
        == 1
    )
    assert (
        result.execution_result["status"]
        == "DEMO_SUCCESS"
    )
    assert (
        result.execution_result["symbol"]
        == "XAUUSD"
    )

    assert runtime.stop() is True


def test_existing_positions_below_limit_are_dispatched():
    bridge, runtime, execution_pipeline = (
        create_bridge(
            max_open_trades=3
        )
    )

    runtime.start()

    result = bridge.execute(
        create_signal(),
        open_position_count=2,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    assert result.status == "executed"
    assert result.task is not None
    assert (
        execution_pipeline.execute_count
        == 1
    )

    runtime.stop()


def test_position_limit_rejection_is_not_dispatched():
    bridge, runtime, execution_pipeline = (
        create_bridge(
            max_open_trades=3
        )
    )

    runtime.start()

    result = bridge.execute(
        create_signal(),
        open_position_count=3,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    assert (
        result.status
        == "decision_rejected"
    )
    assert result.task is None
    assert (
        execution_pipeline.execute_count
        == 0
    )

    runtime.stop()


def test_bridge_requires_runtime_start():
    bridge, _, _ = create_bridge()

    with pytest.raises(
        RuntimeError,
        match="not running",
    ):
        bridge.execute(
            create_signal(),
            open_position_count=0,
            spread_ok=True,
            market_open=True,
            risk_ok=True,
        )


def test_execution_failure_is_recorded():
    class FailingExecutionPipeline:
        def execute(self, plan):
            raise RuntimeError(
                "Demo execution failed."
            )

    runtime = TradingRuntime(
        execution_pipeline=(
            FailingExecutionPipeline()
        )
    )

    producer = TelegramTaskProducer(
        create_profile()
    )

    bridge = TelegramTaskExecutionBridge(
        producer=producer,
        runtime=runtime,
    )

    runtime.start()

    result = bridge.execute(
        create_signal(),
        open_position_count=0,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    assert (
        result.status
        == "execution_failed"
    )
    assert result.task is not None
    assert (
        result.task.status
        == TaskStatus.FAILED
    )
    assert (
        "Demo execution failed."
        in result.errors
    )

    runtime.stop()


def test_bridge_uses_supplied_runtime():
    bridge, runtime, _ = create_bridge()

    assert bridge.runtime is runtime


def test_bridge_rejects_invalid_runtime():
    producer = TelegramTaskProducer(
        create_profile()
    )

    with pytest.raises(
        TypeError,
        match="requires TradingRuntime",
    ):
        TelegramTaskExecutionBridge(
            producer=producer,
            runtime="not-a-runtime",
        )