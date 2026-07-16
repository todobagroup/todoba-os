"""
TODOBA Telegram Task Execution Bridge

Converts approved Telegram signals into organizational
Tasks and dispatches them through the Trading Department.

The bridge does not own trading infrastructure.
"""

from dataclasses import dataclass
from typing import Any, Optional

from backend.integrations.telegram_task_producer import (
    TelegramTaskProducer,
    TelegramTaskProductionResult,
)
from backend.task.task import Task
from backend.trading.department.trading_department import (
    TradingDepartment,
)
from backend.trading.runtime.trading_runtime import (
    TradingRuntime,
)
from backend.trading.signal.incoming_signal import (
    IncomingSignal,
)


@dataclass(frozen=True)
class TelegramTaskExecutionResult:
    """
    Structured Telegram task execution result.
    """

    status: str
    production: TelegramTaskProductionResult
    task: Optional[Task] = None
    execution_result: Optional[Any] = None
    errors: tuple[str, ...] = ()


class TelegramTaskExecutionBridge:
    """
    Dispatch Telegram-produced Tasks through Trading.

    TradingDepartment is the preferred owner.

    Direct TradingRuntime injection remains temporarily
    supported for migration compatibility.
    """

    def __init__(
        self,
        *,
        producer: TelegramTaskProducer,
        department: Optional[
            TradingDepartment
        ] = None,
        runtime: Optional[
            TradingRuntime
        ] = None,
    ):
        if not isinstance(
            producer,
            TelegramTaskProducer,
        ):
            raise TypeError(
                "TelegramTaskExecutionBridge requires "
                "TelegramTaskProducer."
            )

        if (
            department is not None
            and runtime is not None
        ):
            raise ValueError(
                "Provide department or runtime, not both."
            )

        if (
            department is None
            and runtime is None
        ):
            raise ValueError(
                "TelegramTaskExecutionBridge requires "
                "TradingDepartment or TradingRuntime."
            )

        if (
            department is not None
            and not isinstance(
                department,
                TradingDepartment,
            )
        ):
            raise TypeError(
                "department must be TradingDepartment."
            )

        if (
            runtime is not None
            and not isinstance(
                runtime,
                TradingRuntime,
            )
        ):
            raise TypeError(
                "TelegramTaskExecutionBridge requires "
                "TradingRuntime."
            )

        self.producer = producer
        self.department = department

        self.runtime = (
            department.runtime
            if department is not None
            else runtime
        )

        self.queue = self.runtime.queue
        self.registry = self.runtime.registry
        self.worker = self.runtime.worker
        self.dispatcher = self.runtime.dispatcher

    @property
    def running(self) -> bool:
        """
        Report Trading execution state.
        """

        return self.runtime.running

    def start(self) -> bool:
        """
        Start Runtime for migration compatibility.

        Production boot belongs to TradingDepartment.
        """

        return self.runtime.start()

    def stop(self) -> bool:
        """
        Stop Runtime for migration compatibility.

        Production shutdown belongs to TradingDepartment.
        """

        return self.runtime.stop()

    def execute(
        self,
        incoming_signal: IncomingSignal,
        *,
        open_position_count: int,
        spread_ok: bool,
        market_open: bool,
        risk_ok: bool,
    ) -> TelegramTaskExecutionResult:
        """
        Produce and dispatch one organizational Task.
        """

        if not self.runtime.running:
            raise RuntimeError(
                "TelegramTaskExecutionBridge is not running."
            )

        production = self.producer.produce(
            incoming_signal,
            open_position_count=(
                open_position_count
            ),
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
            execution_result = (
                self.runtime.dispatch(
                    task
                )
            )

            return TelegramTaskExecutionResult(
                status="executed",
                production=production,
                task=task,
                execution_result=(
                    execution_result
                ),
            )

        except Exception as error:
            return TelegramTaskExecutionResult(
                status="execution_failed",
                production=production,
                task=task,
                errors=(str(error),),
            )