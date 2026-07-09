import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from backend.task.task_factory import TaskFactory
from backend.task.task_queue import TaskQueue
from backend.task.task_dispatcher import TaskDispatcher
from backend.task.task_status import TaskStatus
from backend.workers.worker_registry import WorkerRegistry


class TradingWorker:

    def execute(self, task):

        return {
            "symbol": "XAUUSD",
            "action": "BUY",
            "message": task.payload,
        }


def main():

    print("=== TASK ENGINE E2E TEST ===")


    queue = TaskQueue()

    registry = WorkerRegistry()


    registry.register(
        "trade",
        TradingWorker()
    )


    task = TaskFactory.create(
        task_type="trade",
        payload="BUY GOLD"
    )


    queue.push(task)


    dispatcher = TaskDispatcher(
        queue,
        registry
    )


    result = dispatcher.dispatch_next()


    print(task.status)

    print(task.worker)

    print(result)

    print(task.status == TaskStatus.COMPLETED)

    print(queue.size() == 0)



if __name__ == "__main__":
    main()