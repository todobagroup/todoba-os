import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.brain.models.experience import Experience
from backend.brain.planner import planner


def main():
    experience = Experience(
        source="telegram",
        content="""
BUY GOLD
SL 3300
TP 3360
"""
    )

    task = planner.plan(experience)

    if task is None:
        print("❌ Planner did not create a Task.")
    else:
        print("✅ Planner created a Task.")
        print(task)


if __name__ == "__main__":
    main()