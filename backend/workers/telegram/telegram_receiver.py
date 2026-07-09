"""
TODOBA Telegram Receiver

Converts raw Telegram messages into IncomingSignal objects.
"""

from datetime import datetime

from backend.trading.signal.incoming_signal import IncomingSignal


class TelegramReceiver:

    def receive(self, message: str, sender: str = None):

        if not message:
            raise ValueError("Telegram message is required.")

        return IncomingSignal(
            source="telegram",
            message=message,
            received_at=datetime.now(),
            sender=sender,
        )