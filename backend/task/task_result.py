"""
TODOBA Task Result

Standard output from worker execution.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class TaskResult:

    success: bool

    worker: str

    message: str

    data: Any

    created_at: datetime