"""
TODOBA Telegram Client

Creates Telegram connections.
"""

from telethon import TelegramClient

from backend.config import (
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_SESSION,
)


def create_telegram_client() -> TelegramClient:
    return TelegramClient(
        TELEGRAM_SESSION,
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH,
    )