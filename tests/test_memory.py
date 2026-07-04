import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.brain.memory import memory_engine
from backend.brain.models.experience import Experience
from backend.brain.models.task import Task


def main():
    print("=== MEMORY CAPABILITY TEST ===")
    print("Capability: Memory Preservation")

    experience = Experience(
        source="telegram",
        content="BUY GOLD\nSL 3300\nTP 3360",
    )

    task = Task(
        title="Review Trading Plan",
        description=experience.content,
        department="Trading Operation",
       
    )

    memory_engine.save(experience)
    memory_engine.save(task)

    saved_experience = memory_engine.get(experience.experience_id)
    saved_task = memory_engine.get(task.task_id)

    print(f"Experience Saved: {saved_experience is not None}")
    print(f"Task Saved: {saved_task is not None}")
    print(f"Memory Size: {len(memory_engine.list())}")


if __name__ == "__main__":
    main()