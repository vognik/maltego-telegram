"""
High-performance MTProto Client Manager for Pyrogram.
Manages persistent connection, session lifecycle, and execution across transforms.
Supports simultaneous execution across multiple Maltego entities and transforms.
"""

import asyncio
import atexit
import base64
import logging
import pathlib
import random
import sqlite3
import struct
import threading
from typing import Any, Coroutine, Optional

# Ensure an event loop exists before Pyrogram import (required for Python 3.10+)
try:
    _loop = asyncio.get_event_loop()
    if _loop.is_closed():
        raise RuntimeError("Loop is closed")
except RuntimeError:
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

from pyrogram import Client
from pyrogram.errors import FloodWait
from pyrogram.storage.storage import Storage

from settings import API_ID, API_HASH, SESSION_NAME, TIMEOUT

logger = logging.getLogger("maltego_telegram.client")

_client: Optional[Client] = None
_client_lock = threading.Lock()
_start_lock: Optional[asyncio.Lock] = None


def _load_session_string(session_file: pathlib.Path) -> Optional[str]:
    """
    Safely extract credentials from a .session file in read-only mode.
    Enables concurrent multi-process execution with zero SQLite database locks.
    """
    if not session_file.is_file():
        return None
    try:
        uri = f"file:{session_file.resolve().as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            row = conn.execute(
                "SELECT dc_id, api_id, test_mode, auth_key, user_id, is_bot FROM sessions"
            ).fetchone()
            if row and row[3]:
                packed = struct.pack(
                    Storage.SESSION_STRING_FORMAT,
                    row[0],
                    row[1] or 0,
                    bool(row[2]),
                    row[3],
                    row[4] or 0,
                    bool(row[5]),
                )
                return base64.urlsafe_b64encode(packed).decode().rstrip("=")
        finally:
            conn.close()
    except Exception as e:
        logger.debug(f"Unable to read session in read-only mode: {e}")
    return None


def get_client() -> Client:
    """Get or initialize the shared Pyrogram Client instance."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                if not API_ID or not API_HASH:
                    raise ValueError(
                        "Telegram api_id and api_hash must be set in config.ini"
                    )
                session_path = pathlib.Path(f"{SESSION_NAME}.session")
                session_str = _load_session_string(session_path)

                if session_str:
                    _client = Client(
                        name=SESSION_NAME,
                        api_id=API_ID,
                        api_hash=API_HASH,
                        session_string=session_str,
                        in_memory=True,
                        no_updates=True,
                    )
                else:
                    _client = Client(
                        name=SESSION_NAME,
                        api_id=API_ID,
                        api_hash=API_HASH,
                        workdir=".",
                        no_updates=True,
                    )
    return _client


def _stop_client():
    """Cleanly shut down client session on process exit."""
    if _client and _client.is_connected:
        try:
            async def _disconnect():
                await _client.stop()

            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(_disconnect(), loop)
                future.result(timeout=5)
            else:
                loop.run_until_complete(_disconnect())
        except Exception:
            pass


atexit.register(_stop_client)


def run_telegram(coro: Coroutine[Any, Any, Any], timeout: Optional[float] = None) -> Any:
    """
    Execute a coroutine synchronously with an active MTProto connection.
    Automatically starts the client if not connected and handles FloodWait.
    """
    client = get_client()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    effective_timeout = timeout or TIMEOUT or 30.0

    async def _execute():
        global _start_lock
        if _start_lock is None:
            _start_lock = asyncio.Lock()

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if not client.is_connected:
                    async with _start_lock:
                        if not client.is_connected:
                            # Random micro-jitter to prevent synchronized bursts on Telegram MTProto
                            await asyncio.sleep(random.uniform(0.05, 0.25))
                            await client.start()
                return await coro
            except FloodWait as e:
                logger.warning(
                    f"Telegram FloodWait encountered: {e.value}s (attempt {attempt + 1}/{max_retries})"
                )
                if attempt < max_retries - 1 and e.value <= effective_timeout:
                    await asyncio.sleep(e.value + 0.5)
                    continue
                raise

    if loop.is_running():
        future = asyncio.run_coroutine_threadsafe(_execute(), loop)
        return future.result(timeout=effective_timeout)
    else:
        return loop.run_until_complete(_execute())
