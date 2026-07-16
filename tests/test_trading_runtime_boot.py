"""
Tests for TODOBA Trading Runtime Boot Sequence.
"""

from pathlib import Path

from backend.trading.execution.live_execution_pipeline import (
    LiveExecutionPipeline,
)
from backend.trading.lifecycle.open_trade_registry import (
    OpenTradeRegistry,
)
from backend.trading.lifecycle.open_trade_repository import (
    OpenTradeRepository,
)
from backend.trading.runtime.runtime_recovery import (
    RuntimeRecovery,
)
from backend.trading.runtime.trading_runtime import (
    TradingRuntime,
)


class FakeExecutionPipeline(
    LiveExecutionPipeline,
):
    """
    Safe pipeline for boot tests.
    """

    def __init__(self):
        pass


def test_runtime_boot_recovers_without_errors(
    tmp_path: Path,
):

    repository = OpenTradeRepository(
        tmp_path / "open_trades.json"
    )

    registry = OpenTradeRegistry()

    recovery = RuntimeRecovery(
        repository=repository,
        registry=registry,
    )

    runtime = TradingRuntime(
        execution_pipeline=FakeExecutionPipeline(),
    )

    assert runtime.start() is True

    restored = recovery.restore()

    assert restored == 0

    assert runtime.stop() is True


def test_runtime_boot_is_repeatable(
    tmp_path: Path,
):

    repository = OpenTradeRepository(
        tmp_path / "open_trades.json"
    )

    registry = OpenTradeRegistry()

    recovery = RuntimeRecovery(
        repository=repository,
        registry=registry,
    )

    runtime = TradingRuntime(
        execution_pipeline=FakeExecutionPipeline(),
    )

    assert runtime.start() is True
    assert runtime.start() is True

    assert recovery.restore() == 0

    assert runtime.stop() is True
    assert runtime.stop() is True