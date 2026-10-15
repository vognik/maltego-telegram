"""
Application settings and configuration loader.
Ensures MTProto environment initialization and loads settings from config.ini.
Supports universal bot naming with fallbacks for maximum extensibility.
"""

import asyncio
import configparser
import os
from typing import Optional, Tuple

# Ensure an event loop exists in the main thread before any Pyrogram import
try:
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        raise RuntimeError("Loop is closed")
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)


class Config:
    """Thread-safe configuration wrapper with sensible defaults."""

    def __init__(self, filename: str = "config.ini"):
        self.config = configparser.ConfigParser()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, filename)

        if os.path.exists(config_path):
            self.config.read(config_path, encoding="utf-8")
        elif os.path.exists(filename):
            self.config.read(filename, encoding="utf-8")

    def get(self, section: str, key: str, fallback: str = "") -> str:
        try:
            val = self.config.get(section, key)
            return val.strip() if val else fallback
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback

    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        try:
            val = self.config.get(section, key).strip()
            return int(val) if val else fallback
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback

    def get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        try:
            return self.config.getboolean(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback

    def get_bot(self, key: str, fallback: str = "") -> str:
        """Get bot login from [bots] section, stripped of @ if present."""
        raw = self.get("bots", key, fallback=fallback)
        if raw and raw.startswith("@"):
            raw = raw[1:]
        return raw.strip()


config = Config()

# Telegram MTProto Credentials
API_ID: int = config.get_int("telegram", "api_id", fallback=0)
API_HASH: str = config.get("telegram", "api_hash", fallback="")
SESSION_NAME: str = config.get("telegram", "session_name", fallback="my_account")

# Universal Bot Logins (Configured ONLY in config.ini)
# user_lookup_bot: Bot to resolve Telegram user ID (e.g. from sticker pack) to username
USER_LOOKUP_BOT: str = config.get_bot("user_lookup_bot") or config.get_bot("tgdb_bot", fallback="usinfobot")

# group_search_bot: Bot to search groups associated with a user profile
GROUP_SEARCH_BOT: str = config.get_bot("group_search_bot") or config.get_bot("tgscan_bot", fallback="tgscanrobot")

# Backwards compatibility aliases
TGDB_BOT: str = USER_LOOKUP_BOT
TGSCAN_BOT: str = GROUP_SEARCH_BOT

# Misc Settings
LIMIT: int = config.get_int("misc", "limit", fallback=100)
if LIMIT <= 0:
    LIMIT = 100

CONCURRENCY: int = config.get_int("misc", "concurrency", fallback=10)
if CONCURRENCY <= 0:
    CONCURRENCY = 10

TIMEOUT: int = config.get_int("misc", "timeout", fallback=15)
if TIMEOUT <= 0:
    TIMEOUT = 15

CONNECTION_TIMEOUT: int = (
    config.get_int("misc", "connection_timeout")
    or config.get_int("misc", "call_timeout", fallback=15)
)
if CONNECTION_TIMEOUT <= 0:
    CONNECTION_TIMEOUT = 15

# TgScan (tgdev.io) API Settings
TGSCAN_TEST_MODE: bool = config.get_bool("tgscan", "test_mode", fallback=False)

TGSCAN_URL_PROD: str = (
    config.get("tgscan", "url_prod")
    or config.get("tgscan", "prod_url", fallback="https://api.tgdev.io/tgscan/v1/search")
)
TGSCAN_URL_TEST: str = (
    config.get("tgscan", "url_test")
    or config.get("tgscan", "test_url", fallback="https://api.tgdev.io/tgscan/v1/test/search")
)

TGSCAN_API_KEY_PROD: str = (
    config.get("tgscan", "api_key_prod")
    or config.get("tgscan", "prod_api_key", fallback="")
)
TGSCAN_API_KEY_TEST: str = (
    config.get("tgscan", "api_key_test")
    or config.get("tgscan", "test_api_key", fallback="")
)


def get_tgscan_credentials(test_mode: Optional[bool] = None) -> Tuple[str, str]:
    """
    Returns (api_url, api_key) for TgScan based on test_mode shortcut.
    If test_mode is True, returns (TGSCAN_URL_TEST, TGSCAN_API_KEY_TEST).
    If test_mode is False, returns (TGSCAN_URL_PROD, TGSCAN_API_KEY_PROD).
    """
    is_test = TGSCAN_TEST_MODE if test_mode is None else test_mode
    if is_test:
        return TGSCAN_URL_TEST, TGSCAN_API_KEY_TEST
    return TGSCAN_URL_PROD, TGSCAN_API_KEY_PROD


