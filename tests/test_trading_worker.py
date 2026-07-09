import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.task.task_factory import TaskFactory
from backend.trading.intent.trading_intent import TradingIntent
from backend.workers.trading.trading_worker import TradingWorker


class DemoExecutionPipeline:

    def execute(self, plan):

        return {
            "status": "SUCCESS",
            "symbol": plan.symbol,
            "order_type": plan.order_type,
            "comment": plan.comment,
        }


def main():

    print("=== TRADING WORKER INTEGRATION TEST ===")

    worker = TradingWorker(
        DemoExecutionPipeline()
    )

    print(worker.start())

    intent = TradingIntent(
        action="BUY",
        asset="GOLD",
        sl=3330,
        tp=3345,
    )

    task = TaskFactory.create(
        task_type="trade",
        payload=intent,
    )

    result = worker.execute(task)

    print(result)

    print(result["status"])

    print(result["symbol"])

    print(result["order_type"])

    print(result["comment"])

    print(worker.stop())


if __name__ == "__main__":
    main()