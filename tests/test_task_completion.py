import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from datetime import datetime

from backend.task.task import Task
from backend.task.task_queue import TaskQueue
from backend.task.task_dispatcher import TaskDispatcher
from backend.task.task_status import TaskStatus
from backend.workers.worker_registry import WorkerRegistry


class TradeWorker:

    def execute(self, task):

        return {
            "symbol": "XAUUSD",
            "action": "BUY",
        }



def main():

    print("=== TASK COMPLETION TEST ===")


    queue = TaskQueue()

    registry = WorkerRegistry()


    registry.register(
        "trade",
        TradeWorker()
    )


    task = Task(
        task_type="trade",
        payload="BUY GOLD",
        created_at=datetime.now(),
    )


    queue.push(task)


    dispatcher = TaskDispatcher(
        queue,
        registry
    )


    dispatcher.dispatch_next()


    print(task.status)

    print(task.result)

    print(task.result["symbol"])

    print(task.status == TaskStatus.COMPLETED)



if __name__ == "__main__":
    main()