import asyncio
from pyrogram import Client
from settings import api_id, api_hash


async def main():
    async with Client("my_account", api_id, api_hash) as app:
        await app.send_message("me", "If you see this message, then everything is OK")


asyncio.run(main())
