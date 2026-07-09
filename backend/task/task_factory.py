"""
TODOBA Task Factory

Creates standardized organizational tasks.
"""

from datetime import datetime

from backend.task.task import Task


class TaskFactory:

    @staticmethod
    def create(task_type, payload):

        return Task(
            task_type=task_type,
            payload=payload,
            created_at=datetime.now(),
        )