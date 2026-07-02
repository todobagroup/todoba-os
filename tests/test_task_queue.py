import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.brain.task_queue import task_queue


def main():
    print("=== TASK QUEUE TEST ===")

    task_queue.add("TASK-001")
    task_queue.add("TASK-002")
    task_queue.add("TASK-003")

    print(f"Queue Size: {task_queue.size()}")

    print(f"Next Task: {task_queue.next_task()}")

    task_queue.remove("TASK-001")

    print(f"Queue Size After Remove: {task_queue.size()}")

    print(f"Next Task: {task_queue.next_task()}")


if __name__ == "__main__":
    main()