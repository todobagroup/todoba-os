"""
TODOBA Trading Runtime

Owns the organizational execution infrastructure of the
Trading Department.

Architecture:

Organizational Task
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

Integrations such as Telegram must not create these
components themselves.
"""

from typing import Any

from backend.task.task import Task
from backend.task.task_dispatcher import TaskDispatcher
from backend.task.task_queue import TaskQueue
from backend.task.task_status import TaskStatus
from backend.workers.trading.trading_worker import (
    TradingWorker,
)
from backend.workers.worker_registry import (
    WorkerRegistry,
)


class TradingRuntime:
    """
    Execute organizational trading tasks.

    The runtime owns:

    - TaskQueue
    - WorkerRegistry
    - TradingWorker
    - TaskDispatcher

    It does not:

    - parse Telegram messages;
    - make trading decisions;
    - connect to Telegram;
    - create MT5 execution pipelines;
    - monitor completed positions.
    """

    def __init__(
        self,
        *,
        execution_pipeline,
    ):
        if execution_pipeline is None:
            raise ValueError(
                "TradingRuntime requires "
                "an execution pipeline."
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
        """
        Start the Trading Department execution runtime.
        """

        if self.running:
            return True

        self.worker.start()
        self.running = True

        return True

    def stop(self) -> bool:
        """
        Stop the Trading Department execution runtime.
        """

        if not self.running:
            return True

        self.worker.stop()
        self.running = False

        return True

    def dispatch(
        self,
        task: Task,
    ) -> Any:
        """
        Queue and execute one organizational trading task.
        """

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

        self.queue.push(
            task
        )

        return self.dispatcher.dispatch_next()