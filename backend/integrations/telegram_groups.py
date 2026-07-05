"""
TODOBA Telegram Group Discovery

List all Telegram groups/channels available to TODOBA.
"""

import asyncio

from backend.integrations.telegram_client import client


async def main():
    print("=== TODOBA TELEGRAM GROUP DISCOVERY ===")

    await client.start()

    async for dialog in client.iter_dialogs():
        print("-----------------------------------")
        print(f"Name: {dialog.name}")
        print(f"ID: {dialog.id}")
        print(f"Is Group: {dialog.is_group}")
        print(f"Is Channel: {dialog.is_channel}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())