import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from datetime import datetime

from backend.task.task import Task
from backend.task.task_queue import TaskQueue
from backend.task.task_dispatcher import TaskDispatcher


def main():

    print("=== TASK DISPATCHER TEST ===")

    queue = TaskQueue()

    queue.push(
        Task(
            task_type="trade",
            payload="BUY GOLD",
            created_at=datetime.now(),
        )
    )

    dispatcher = TaskDispatcher(queue)

    task = dispatcher.next_task()

    print(task.task_type)

    print(queue.size())

    print(task.payload == "BUY GOLD")


if __name__ == "__main__":
    main()