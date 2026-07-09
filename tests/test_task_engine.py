import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from datetime import datetime

from backend.task.task import Task
from backend.task.task_queue import TaskQueue
from backend.task.task_status import TaskStatus
from backend.task.task_dispatcher import TaskDispatcher
from backend.workers.worker_registry import WorkerRegistry


class DemoTradeWorker:

    def execute(self, task):
        return f"executed: {task.payload}"


def main():

    print("=== TASK ENGINE TEST ===")

    queue = TaskQueue()
    registry = WorkerRegistry()

    worker = DemoTradeWorker()

    registry.register("trade", worker)

    task = Task(
        task_type="trade",
        payload="BUY GOLD",
        created_at=datetime.now(),
    )

    task.status = TaskStatus.QUEUED

    queue.push(task)

    dispatcher = TaskDispatcher(queue, registry)

    result = dispatcher.dispatch_next()

    print(result)
    print(task.status)
    print(queue.size())

    print(result == "executed: BUY GOLD")
    print(task.status == TaskStatus.COMPLETED)
    print(queue.size() == 0)


if __name__ == "__main__":
    main()