"""
TODOBA Telegram Listener

Capability 02

Listen only to the configured signal group.
"""

import asyncio

from telethon import events

from backend.integrations.telegram_client import client
from backend.config import TELEGRAM_SIGNAL_GROUP_ID


@client.on(events.NewMessage)
async def new_message(event):

    # Ignore every message outside the signal group
    if event.chat_id != TELEGRAM_SIGNAL_GROUP_ID:
        return

    print()
    print("===================================")
    print("NEW SIGNAL RECEIVED")
    print("===================================")
    print(event.raw_text)
    print("===================================")


async def main():

    print("Starting Telegram Listener...")
    print(f"Watching Group ID: {TELEGRAM_SIGNAL_GROUP_ID}")

    await client.start()

    print("Telegram Listener Running...")

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())