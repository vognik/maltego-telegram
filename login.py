"""
Interactive Telegram MTProto Login Script.
Authorizes the user account and creates the session file for Maltego Transforms.
"""

import sys
import asyncio
from pyrogram import Client
from settings import API_ID, API_HASH, SESSION_NAME


async def main():
    if not API_ID or not API_HASH:
        print("[!] ERROR: api_id and api_hash must be specified in config.ini")
        print("    Get your API credentials at: https://my.telegram.org")
        sys.exit(1)

    print(f"[*] Starting MTProto authorization for session '{SESSION_NAME}'...")
    print(f"[*] api_id: {API_ID}")

    async with Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, workdir=".") as app:
        me = await app.get_me()
        print(f"[+] Successfully authorized as: {me.first_name} (@{me.username or me.id})")
        await app.send_message(
            "me",
            "🚀 Maltego Telegram: Authorization successful! You are ready to run MTProto transforms.",
        )
        print("[+] Test message sent to your 'Saved Messages'.")
        print("[+] Session file generated successfully.")


if __name__ == "__main__":
    asyncio.run(main())
