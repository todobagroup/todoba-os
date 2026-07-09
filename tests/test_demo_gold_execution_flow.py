import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.task.task_factory import TaskFactory
from backend.trading.intent.trading_intent import TradingIntent
from backend.trading.execution.trading_execution_adapter import (
    TradingExecutionAdapter,
)


def main():

    print("=== DEMO GOLD EXECUTION FLOW ===")

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

    adapter = TradingExecutionAdapter()

    plan = adapter.to_execution_plan(task.payload)

    print(plan.symbol)

    print(plan.order_type)

    print(plan.comment)

    print(plan.magic_number)


if __name__ == "__main__":
    main()