from backend.brain.memory.models.experience import Experience


class MemoryEngine:
    """
    Memory Engine receives experiences from the outside world.
    """

    def receive_experience(self, source: str, content: str) -> Experience:
        return Experience(
            source=source,
            content=content,
        )