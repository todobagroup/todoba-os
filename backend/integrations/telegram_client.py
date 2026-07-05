"""
TODOBA Telegram Client

Shared Telegram connection.
"""

from telethon import TelegramClient

from backend.config import (
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_SESSION,
)

client = TelegramClient(
    TELEGRAM_SESSION,
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
)