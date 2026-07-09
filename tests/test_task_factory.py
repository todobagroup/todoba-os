import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


from backend.task.task_factory import TaskFactory
from backend.task.task_status import TaskStatus


def main():

    print("=== TASK FACTORY TEST ===")

    task = TaskFactory.create(
        task_type="trade",
        payload="BUY GOLD",
    )

    print(task.task_type)

    print(task.payload)

    print(task.status)

    print(task.status == TaskStatus.CREATED)


if __name__ == "__main__":
    main()