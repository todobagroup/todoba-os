from backend.brain.memory import memory_engine
from backend.brain.models.experience import Experience
from backend.brain.planner import planner
from backend.brain.task_queue import task_queue


class BrainEngine:
    def process(self, experience: Experience):
        memory_engine.save(experience)

        task = planner.plan(experience)

        if task is not None:
            memory_engine.save(task)
            task_queue.add(task.task_id)

        return task


brain_engine = BrainEngine()