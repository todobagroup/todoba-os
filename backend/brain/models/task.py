from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass
class Task:
    task_id: str = field(default_factory=lambda: str(uuid4()))

    title: str = ""
    description: str = ""

    department: str = ""
    role: str = ""

    status: str = "pending"

    created_at: datetime = field(default_factory=datetime.utcnow)