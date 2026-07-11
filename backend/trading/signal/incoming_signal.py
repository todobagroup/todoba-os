"""
TODOBA Incoming Signal

Represents a normalized signal received from an external source.

Version: 1.1
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class IncomingSignal:
    """
    Standard signal envelope entering TODOBA.

    This object preserves where the message came from before
    the message is interpreted as a trading Signal.
    """

    source: str
    message: str
    received_at: datetime

    sender: Optional[str] = None
    sender_id: Optional[int] = None
    chat_id: Optional[int] = None
    message_id: Optional[int] = None

    def source_key(self) -> Optional[tuple[int, int]]:
        """
        Return a stable Telegram message identity when available.

        Telegram messages are uniquely identified inside a chat by:
        chat_id + message_id.
        """

        if self.chat_id is None or self.message_id is None:
            return None

        return self.chat_id, self.message_id