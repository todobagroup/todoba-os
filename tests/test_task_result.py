import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from datetime import datetime

from backend.task.task_result import TaskResult


def main():

    print("=== TASK RESULT TEST ===")

    result = TaskResult(
        success=True,
        worker="DemoTradeWorker",
        message="BUY GOLD executed",
        data={"symbol": "XAUUSD"},
        created_at=datetime.now(),
    )

    print(result)

    print(result.success)
    print(result.worker)
    print(result.data["symbol"])


if __name__ == "__main__":
    main()