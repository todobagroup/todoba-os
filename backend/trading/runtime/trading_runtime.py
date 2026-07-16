"""
TODOBA Trading Runtime

Owns organizational task execution for the Trading
Department.
"""

from typing import Any, Optional

from backend.task.task import Task
from backend.task.task_dispatcher import TaskDispatcher
from backend.task.task_queue import TaskQueue
from backend.task.task_status import TaskStatus
from backend.trading.lifecycle.open_trade_persistence import (
    OpenTradePersistence,
)
from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)
from backend.trading.lifecycle.trade_timeline_service import (
    TradeTimelineService,
)
from backend.workers.trading.trading_worker import (
    TradingWorker,
)
from backend.workers.worker_registry import (
    WorkerRegistry,
)


class TradingRuntime:
    """
    Execute organizational trading tasks and register
    newly opened trades.
    """

    def __init__(
        self,
        *,
        execution_pipeline,
        open_trade_persistence: Optional[
            OpenTradePersistence
        ] = None,
        timeline_service: Optional[
            TradeTimelineService
        ] = None,
    ):
        if execution_pipeline is None:
            raise ValueError(
                "TradingRuntime requires "
                "an execution pipeline."
            )

        if (
            open_trade_persistence is not None
            and not isinstance(
                open_trade_persistence,
                OpenTradePersistence,
            )
        ):
            raise TypeError(
                "open_trade_persistence must be "
                "OpenTradePersistence."
            )

        if (
            timeline_service is not None
            and not isinstance(
                timeline_service,
                TradeTimelineService,
            )
        ):
            raise TypeError(
                "timeline_service must be "
                "TradeTimelineService."
            )

        self.open_trade_persistence = (
            open_trade_persistence
        )

        self.timeline_service = (
            timeline_service
        )

        self.queue = TaskQueue()
        self.registry = WorkerRegistry()

        self.worker = TradingWorker(
            execution_pipeline
        )

        self.registry.register(
            "trade",
            self.worker,
        )

        self.dispatcher = TaskDispatcher(
            self.queue,
            self.registry,
        )

        self.running = False

    def start(self) -> bool:
        if self.running:
            return True

        self.worker.start()
        self.running = True

        return True

    def stop(self) -> bool:
        if not self.running:
            return True

        self.worker.stop()
        self.running = False

        return True

    def register_open_trade(
        self,
        trade_record: TradeRecord,
    ) -> TradeRecord:
        """
        Register one newly opened organizational trade.

        The trade may originate from immediate execution
        or pending-order activation.
        """

        if not isinstance(
            trade_record,
            TradeRecord,
        ):
            raise TypeError(
                "register_open_trade requires "
                "TradeRecord."
            )

        if (
            self.open_trade_persistence
            is not None
        ):
            self.open_trade_persistence.persist(
                trade_record
            )

        if (
            self.timeline_service
            is not None
        ):
            self.timeline_service.start_trade(
                trade_record.trade_id
            )

        return trade_record

    def dispatch(
        self,
        task: Task,
    ) -> Any:
        if not self.running:
            raise RuntimeError(
                "TradingRuntime is not running."
            )

        if not isinstance(
            task,
            Task,
        ):
            raise TypeError(
                "TradingRuntime requires Task."
            )

        if task.task_type != "trade":
            raise ValueError(
                "TradingRuntime only accepts "
                "trade tasks."
            )

        task.status = TaskStatus.QUEUED

        self.queue.push(task)

        execution_result = (
            self.dispatcher.dispatch_next()
        )

        if isinstance(
            execution_result,
            TradeRecord,
        ):
            self.register_open_trade(
                execution_result
            )

        return execution_result