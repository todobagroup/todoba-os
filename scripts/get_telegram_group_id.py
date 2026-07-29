import asyncio

from telethon import TelegramClient

from backend.config import (
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_SESSION,
)


async def main() -> None:
    async with TelegramClient(
        TELEGRAM_SESSION,
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH,
    ) as client:
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                print(dialog.id, "|", dialog.name)


if __name__ == "__main__":
    asyncio.run(main())