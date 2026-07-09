"""
TODOBA Task

Base task shared by the whole organization.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from backend.task.task_status import TaskStatus


@dataclass
class Task:

    task_type: str

    payload: Any

    created_at: datetime

    status: TaskStatus = TaskStatus.CREATED

    result: Optional[Any] = None

    worker: Optional[str] = None

    started_at: Optional[datetime] = None

    completed_at: Optional[datetime] = None