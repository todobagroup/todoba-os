from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass
class Experience:
    experience_id: str = field(default_factory=lambda: str(uuid4()))
    source: str = ""
    content: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)