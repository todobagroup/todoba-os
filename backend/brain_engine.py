from pathlib import Path


class BrainEngine:

    def __init__(self):
        self.brain_path = Path("backend/brain")

    def list_memory(self):

        memories = []

        for file in self.brain_path.rglob("*.md"):
            memories.append(file)

        return memories