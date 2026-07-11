"""
TODOBA Telegram Receiver

Converts raw Telegram messages into IncomingSignal objects.
"""

from datetime import datetime, timezone
from typing import Optional

from backend.trading.signal.incoming_signal import IncomingSignal


class TelegramReceiver:
    """
    Boundary between Telegram transport data and TODOBA.

    This receiver does not parse trading instructions.
    It only validates and normalizes Telegram message metadata.
    """

    def receive(
        self,
        message: str,
        sender: Optional[str] = None,
        sender_id: Optional[int] = None,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
    ) -> IncomingSignal:
        normalized_message = message.strip() if message else ""

        if not normalized_message:
            raise ValueError(
                "Telegram message is required."
            )

        normalized_sender = (
            sender.strip()
            if sender and sender.strip()
            else None
        )

        return IncomingSignal(
            source="telegram",
            message=normalized_message,
            received_at=datetime.now(timezone.utc),
            sender=normalized_sender,
            sender_id=sender_id,
            chat_id=chat_id,
            message_id=message_id,
        )