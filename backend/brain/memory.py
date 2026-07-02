from backend.brain.models.experience import Experience


class MemoryEngine:
    def __init__(self):
        self.memories: list[Experience] = []

    def remember(self, experience: Experience) -> Experience:
        self.memories.append(experience)
        return experience

    def list_memories(self) -> list[Experience]:
        return self.memories

    def recall(self, keyword: str) -> list[Experience]:
        results = []

        for memory in self.memories:
            if keyword.lower() in memory.content.lower():
                results.append(memory)

        return results


memory_engine = MemoryEngine()