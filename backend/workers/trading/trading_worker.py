"""
TODOBA Trading Worker

Executes trading tasks using the Execution Pipeline.
"""

from backend.workers.worker import Worker
from backend.trading.execution.trading_execution_adapter import (
    TradingExecutionAdapter,
)


class TradingWorker(Worker):

    def __init__(self, execution_pipeline):

        self.execution_pipeline = execution_pipeline
        self.adapter = TradingExecutionAdapter()
        self.running = False


    def start(self):

        self.running = True
        return True


    def stop(self):

        self.running = False
        return True


    def execute(self, task):

        if not self.running:
            raise RuntimeError("TradingWorker is not running.")

        plan = self.adapter.to_execution_plan(
            task.payload
        )

        return self.execution_pipeline.execute(plan)