import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.brain.models.experience import Experience
from backend.brain_engine import brain_engine
from backend.brain.memory import memory_engine


def main():

    print("=== BRAIN ENGINE CAPABILITY TEST ===")
    print("Capability: Experience Processing")

    experience = Experience(
        source="telegram",
        content="""
BUY GOLD
SL 3300
TP 3360
""",
    )

    task = brain_engine.process(experience)

    print(f"Task Created: {task is not None}")

    if task is not None:
        print(f"Task Title: {task.title}")
        print(f"Department: {task.department}")

    print(f"Memory Objects: {len(memory_engine.list())}")


if __name__ == "__main__":
    main()