import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from datetime import datetime

from backend.task.task import Task
from backend.task.task_status import TaskStatus


def main():

    print("=== TASK TEST ===")

    task = Task(
        task_type="trade",
        payload="BUY GOLD",
        created_at=datetime.now(),
    )

    print(task.status)

    task.status = TaskStatus.QUEUED
    print(task.status)

    task.status = TaskStatus.RUNNING
    print(task.status)

    task.status = TaskStatus.COMPLETED
    print(task.status)

    print(task.status == TaskStatus.COMPLETED)


if __name__ == "__main__":
    main()