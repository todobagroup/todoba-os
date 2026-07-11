"""
TODOBA Telegram Task Execution Bridge

Connects Telegram-produced organizational Tasks to the
Trading Department Runtime.

Architecture:

TelegramTaskProducer
        ↓
Organizational Task
        ↓
TradingRuntime
        ↓
TaskQueue
        ↓
TaskDispatcher
        ↓
WorkerRegistry
        ↓
TradingWorker
        ↓
Execution Pipeline

The bridge owns Telegram translation and structured results.

The TradingRuntime owns organizational trade execution.
"""

from dataclasses import dataclass
from typing import Any, Optional

from backend.integrations.telegram_task_producer import (
    TelegramTaskProducer,
    TelegramTaskProductionResult,
)
from backend.task.task import Task
from backend.trading.runtime.trading_runtime import (
    TradingRuntime,
)
from backend.trading.signal.incoming_signal import (
    IncomingSignal,
)


@dataclass(frozen=True)
class TelegramTaskExecutionResult:
    """
    Structured outcome of Telegram organizational execution.
    """

    status: str
    production: TelegramTaskProductionResult
    task: Optional[Task] = None
    execution_result: Optional[Any] = None
    errors: tuple[str, ...] = ()


class TelegramTaskExecutionBridge:
    """
    Produce Telegram trading Tasks and dispatch them through
    the TradingRuntime.

    Telegram does not execute trades directly.

    The bridge does not own:

    - TaskQueue
    - WorkerRegistry
    - TradingWorker
    - TaskDispatcher
    - Execution Pipeline
    """

    def __init__(
        self,
        *,
        producer: TelegramTaskProducer,
        runtime: TradingRuntime,
    ):
        if not isinstance(
            producer,
            TelegramTaskProducer,
        ):
            raise TypeError(
                "TelegramTaskExecutionBridge requires "
                "TelegramTaskProducer."
            )

        if not isinstance(
            runtime,
            TradingRuntime,
        ):
            raise TypeError(
                "TelegramTaskExecutionBridge requires "
                "TradingRuntime."
            )

        self.producer = producer
        self.runtime = runtime

        # Temporary compatibility aliases.
        #
        # Existing code and tests may still inspect these
        # attributes during the migration. The Bridge does not
        # create or own them; TradingRuntime remains the owner.
        self.queue = runtime.queue
        self.registry = runtime.registry
        self.worker = runtime.worker
        self.dispatcher = runtime.dispatcher

    @property
    def running(self) -> bool:
        """
        Report the state of the TradingRuntime.
        """

        return self.runtime.running

    def start(self) -> bool:
        """
        Start the TradingRuntime.

        This compatibility method will be removed from the
        Bridge after runtime ownership migration is complete.
        """

        return self.runtime.start()

    def stop(self) -> bool:
        """
        Stop the TradingRuntime.

        This compatibility method will be removed from the
        Bridge after runtime ownership migration is complete.
        """

        return self.runtime.stop()

    def execute(
        self,
        incoming_signal: IncomingSignal,
        *,
        has_open_position: bool,
        spread_ok: bool,
        market_open: bool,
        risk_ok: bool,
    ) -> TelegramTaskExecutionResult:
        """
        Produce and dispatch one organizational trading Task.
        """

        if not self.runtime.running:
            raise RuntimeError(
                "TelegramTaskExecutionBridge is not running."
            )

        production = self.producer.produce(
            incoming_signal,
            has_open_position=has_open_position,
            spread_ok=spread_ok,
            market_open=market_open,
            risk_ok=risk_ok,
        )

        if production.task is None:
            return TelegramTaskExecutionResult(
                status=production.status,
                production=production,
                errors=production.errors,
            )

        task = production.task

        try:
            execution_result = self.runtime.dispatch(
                task
            )

            return TelegramTaskExecutionResult(
                status="executed",
                production=production,
                task=task,
                execution_result=execution_result,
            )

        except Exception as error:
            return TelegramTaskExecutionResult(
                status="execution_failed",
                production=production,
                task=task,
                errors=(str(error),),
            )