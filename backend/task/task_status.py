"""
TODOBA Task Status

Represents lifecycle of an organizational task.
"""

from enum import Enum


class TaskStatus(Enum):

    CREATED = "created"

    QUEUED = "queued"

    RUNNING = "running"

    COMPLETED = "completed"

    FAILED = "failed"