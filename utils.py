"""
Utility helpers for Maltego Telegram Transforms.
100% MTProto-based media fetching, entity building, and bot interactions.
Zero Bot API, zero bot_token, zero web scraping.
"""

import asyncio
import base64
from io import BytesIO
import logging
import re
from typing import Any, Dict, List, Optional

from PIL import Image
from pyrogram import Client
from pyrogram.enums import MessageEntityType
from pyrogram.raw import functions, types as raw_types
from pyrogram.types import Message, User
from maltego_trx.maltego import MaltegoEntity, MaltegoMsg

logger = logging.getLogger("maltego_telegram.utils")

# Telegram profile color palette for default avatars
PALETTE = [
    "#d45246",  # Red
    "#46ba43",  # Green
    "#e5ca77",  # Yellow
    "#408acf",  # Blue
    "#6c61df",  # Purple
    "#d95574",  # Pink
    "#359ad4",  # Sea
    "#f68136",  # Orange
]

MAP = [0, 7, 4, 1, 6, 3, 5]

# In-memory caches to prevent duplicate MTProto network calls
_avatar_cache: Dict[str, str] = {}
_sticker_thumb_cache: Dict[str, str] = {}
_chat_cache: Dict[str, Any] = {}


def get_color(profile_id: int) -> str:
    """Determine Telegram accent color from profile/chat ID."""
    return PALETTE[MAP[abs(profile_id) % len(MAP)]]


def get_default_photo_b64(profile_id: int, size: int = 64) -> str:
    """Generate default solid color avatar base64 for profiles without a photo."""
    color = get_color(profile_id)
    img = Image.new("RGB", (size, size), color)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def normalize_identifier(value: Optional[str]) -> str:
    """
    Normalize Telegram username or channel identifier.
    Strips https://t.me/, t.me/, @ and whitespace.
    """
    if not value:
        return ""
    val = value.strip()
    val = re.sub(r"^https?://(?:www\.)?t\.me/", "", val, flags=re.IGNORECASE)
    val = re.sub(r"^t\.me/", "", val, flags=re.IGNORECASE)
    val = val.lstrip("@").strip("/ ")
    return val


def normalize_phone(phone: Optional[str]) -> str:
    """Clean phone number keeping only digits and optional leading +."""
    if not phone:
        return ""
    val = phone.strip()
    has_plus = val.startswith("+")
    digits = re.sub(r"\D", "", val)
    return f"+{digits}" if has_plus else digits


def safe_get_property(request: MaltegoMsg, prop_name: str, fallback: Optional[str] = None) -> str:
    """Safely retrieve a specific property from Maltego request."""
    val = request.getProperty(prop_name)
    if val is not None and str(val).strip():
        return str(val).strip()
    return fallback or ""


def safe_get_identifier(request: MaltegoMsg, prop_name: Optional[str] = None, fallback: str = "") -> str:
    """
    Safely retrieve the primary identifier (channel, username, phone, etc.).
    Checks prop_name first, falls back to request.Value.
    """
    if prop_name:
        val = request.getProperty(prop_name)
        if val is not None and str(val).strip():
            return str(val).strip()
    if request.Value is not None and str(request.Value).strip():
        return str(request.Value).strip()
    return fallback


def message_is_forwarded_from_another_chat(message: Message, username: str) -> bool:
    """Check if message is forwarded from another chat."""
    clean_username = normalize_identifier(username).lower()
    if getattr(message, "forward_from_chat", None):
        fwd_user = normalize_identifier(getattr(message.forward_from_chat, "username", "")).lower()
        if fwd_user and fwd_user != clean_username:
            return True
        fwd_title = getattr(message.forward_from_chat, "title", "").lower()
        if fwd_title and fwd_title != clean_username:
            return True
    return False


async def download_avatar_b64(client: Client, entity_obj: Any) -> Optional[str]:
    """
    Download profile or chat avatar via MTProto and return base64 encoded PNG/JPEG.
    Uses in-memory cache to avoid duplicate MTProto RPC downloads.
    """
    if not entity_obj:
        return None

    entity_id = getattr(entity_obj, "id", None)
    cache_key = f"avatar_{entity_id}"
    if cache_key in _avatar_cache:
        return _avatar_cache[cache_key]

    photo = getattr(entity_obj, "photo", None)
    if not photo:
        if entity_id:
            default_b64 = get_default_photo_b64(entity_id)
            _avatar_cache[cache_key] = default_b64
            return default_b64
        return None

    file_id = getattr(photo, "small_file_id", None) or getattr(photo, "big_file_id", None)
    if not file_id:
        return None

    try:
        data = await client.download_media(file_id, in_memory=True)
        if data and hasattr(data, "getbuffer"):
            b64 = base64.b64encode(bytes(data.getbuffer())).decode("utf-8")
            _avatar_cache[cache_key] = b64
            return b64
    except Exception as e:
        logger.debug(f"Failed to download avatar via MTProto for {entity_id}: {e}")

    if entity_id:
        return get_default_photo_b64(entity_id)
    return None


async def get_sticker_set_thumbnail_b64(client: Client, short_name: str) -> Optional[str]:
    """
    Retrieve sticker pack thumbnail via MTProto raw GetStickerSet.
    Pure MTProto: downloads thumb or first sticker and returns base64.
    """
    clean_name = short_name.strip()
    if clean_name in _sticker_thumb_cache:
        return _sticker_thumb_cache[clean_name]

    try:
        sticker_set = await client.invoke(
            functions.messages.GetStickerSet(
                stickerset=raw_types.InputStickerSetShortName(short_name=clean_name),
                hash=0,
            )
        )
        if not sticker_set:
            return None

        # Try set thumbs first
        target_media = None
        if getattr(sticker_set.set, "thumbs", None):
            target_media = sticker_set.set.thumbs[0]
        elif sticker_set.documents:
            target_media = sticker_set.documents[0]

        if target_media:
            data = await client.download_media(target_media, in_memory=True)
            if data and hasattr(data, "getbuffer"):
                b64 = base64.b64encode(bytes(data.getbuffer())).decode("utf-8")
                _sticker_thumb_cache[clean_name] = b64
                return b64
    except Exception as e:
        logger.debug(f"Failed to fetch sticker set thumb via MTProto for {clean_name}: {e}")

    return None


async def get_custom_emoji_thumbnail_b64(client: Client, emoji_id: int) -> Optional[str]:
    """
    Retrieve custom emoji thumbnail via MTProto get_custom_emoji_stickers.
    Pure MTProto: downloads thumb or emoji sticker and returns base64.
    """
    cache_key = f"emoji_{emoji_id}"
    if cache_key in _sticker_thumb_cache:
        return _sticker_thumb_cache[cache_key]

    try:
        stickers = await client.get_custom_emoji_stickers(custom_emoji_ids=[emoji_id])
        if stickers:
            sticker = stickers[0]
            thumb_target = sticker.thumbs[0] if getattr(sticker, "thumbs", None) else sticker
            data = await client.download_media(thumb_target, in_memory=True)
            if data and hasattr(data, "getbuffer"):
                b64 = base64.b64encode(bytes(data.getbuffer())).decode("utf-8")
                _sticker_thumb_cache[cache_key] = b64
                return b64
    except Exception as e:
        logger.debug(f"Failed to fetch custom emoji thumb via MTProto for {emoji_id}: {e}")

    return None


def create_maltego_entity(entity_type: str, obj: Any) -> MaltegoEntity:
    """Create a MaltegoEntity from a Pyrogram object or dict."""
    identity = getattr(obj, "username", None) or getattr(obj, "id", None) or "Unknown"
    entity = MaltegoEntity(entity_type, str(identity))

    exclude_keys = {"raw", "photo", "_client", "usernames", "thumbs"}

    if isinstance(obj, dict):
        attributes = obj.items()
    elif hasattr(obj, "__dict__"):
        attributes = vars(obj).items()
    elif hasattr(obj, "__slots__"):
        attributes = [(attr, getattr(obj, attr)) for attr in obj.__slots__]
    else:
        return entity

    for key, value in attributes:
        if key and value is not None and key not in exclude_keys and not str(key).startswith("_"):
            entity.addProperty(f"properties.{key}", value=str(value))

    return entity


def process_profile_entity(user: User, avatar_b64: Optional[str] = None) -> MaltegoEntity:
    """Build a standard Maltego UserProfile entity with properties and avatar."""
    identity = user.username or str(user.id)
    entity = MaltegoEntity("interlinked.telegram.UserProfile", value=identity)

    entity.addProperty("properties.id", value=str(user.id))
    if user.username:
        entity.addProperty("properties.username", value=user.username)
    if user.first_name:
        entity.addProperty("properties.first_name", value=user.first_name)
    if user.last_name:
        entity.addProperty("properties.last_name", value=user.last_name)
    if getattr(user, "phone_number", None):
        entity.addProperty("properties.phone", value=user.phone_number)

    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    if full_name:
        entity.addProperty("properties.full_name", value=full_name)

    if avatar_b64:
        entity.addProperty("base64", value=avatar_b64)
    else:
        entity.addProperty("base64", value=get_default_photo_b64(user.id))

    return entity


# --- MTProto Bot Query Helpers ---

async def query_inline_bot(client: Client, bot_username: str, query_text: str) -> List[Any]:
    """
    Query a bot via MTProto inline query (e.g. tgdb_search_bot).
    Returns list of inline query results.
    """
    clean_bot = normalize_identifier(bot_username)
    if not clean_bot:
        return []
    try:
        inline_search = await client.get_inline_bot_results(clean_bot, query_text)
        return inline_search.results if inline_search else []
    except Exception as e:
        logger.warning(f"MTProto inline query to bot @{clean_bot} failed: {e}")
        return []


async def query_bot_dialog(
    client: Client,
    bot_username: str,
    query_text: str,
    timeout: float = 12.0,
) -> Optional[Message]:
    """
    Query a bot via MTProto direct message dialog (e.g. tgscanrobot).
    Sends the message and awaits the bot's response message.
    """
    clean_bot = normalize_identifier(bot_username)
    if not clean_bot:
        return None

    try:
        sent = await client.send_message(clean_bot, query_text)
        sent_id = sent.id

        # Poll for bot response with timeout
        elapsed = 0.0
        poll_interval = 1.0

        while elapsed < timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            async for msg in client.get_chat_history(clean_bot, limit=5):
                if msg.id > sent_id and not msg.outgoing:
                    return msg

    except Exception as e:
        logger.warning(f"MTProto message dialog with bot @{clean_bot} failed: {e}")

    return None


def extract_group_links_from_text(text: str, entities: Optional[List[Any]] = None) -> List[str]:
    """
    Extract group usernames or invite links from a bot's response message.
    """
    results = set()
    if not text:
        return []

    # 1. Regex find all @usernames
    mentions = re.findall(r"@([a-zA-Z0-9_]{4,})", text)
    for m in mentions:
        results.add(m)

    # 2. Regex find all t.me links
    links = re.findall(r"(?:https?://)?t\.me/([a-zA-Z0-9_]{4,})", text)
    for l in links:
        results.add(l)

    # 3. Message entities if available
    if entities:
        for ent in entities:
            if ent.type == MessageEntityType.TEXT_LINK and getattr(ent, "url", None):
                m = re.search(r"t\.me/([a-zA-Z0-9_]{4,})", ent.url)
                if m:
                    results.add(m.group(1))

    return list(results)


def extract_username_from_text(text: str) -> Optional[str]:
    """
    Extract username/login matching Telegram login regex from bot response text.
    Handles responses from bot dialogs:
    - Lines with symbol prefix: '🌐 @username'
    - Standard mentions: '@username'
    - Links: 't.me/username'
    - Labeled lines: 'Username: username', 'Login: username'
    """
    if not text:
        return None

    # Clean invisible unicode characters (e.g. \u2063 invisible separator used by some bots)
    cleaned = re.sub(r"[\u200b-\u200f\u2060-\u206f]", "", text)

    # 1. Match symbol prefix followed by @username (e.g. '🌐 @username')
    symbol_match = re.search(r"[🌐👤👦🏻👦👧👨👩]\s*@?([a-zA-Z0-9_]{4,32})\b", cleaned)
    if symbol_match:
        cand = symbol_match.group(1).lstrip("@")
        if not cand.isdigit() and cand.lower() not in {"user", "bot", "none"}:
            return cand

    # 2. Match standard @username
    at_match = re.search(r"@([a-zA-Z0-9_]{4,32})\b", cleaned)
    if at_match:
        return at_match.group(1)

    # 3. Match t.me/username
    tme_match = re.search(r"(?:https?://)?t\.me/([a-zA-Z0-9_]{4,32})\b", cleaned)
    if tme_match:
        return tme_match.group(1)

    # 4. Match label 'username: <name>' or 'login: <name>' or 'user: <name>'
    label_match = re.search(
        r"(?:username|login|user)\s*[:=]\s*@?([a-zA-Z0-9_]{4,32})\b",
        cleaned,
        re.IGNORECASE,
    )
    if label_match:
        return label_match.group(1)

    # 5. Line-by-line fallback regex for standalone login
    for line in cleaned.splitlines():
        line = line.strip().strip("`*_\":, \t")
        m = re.match(r"^@?([a-zA-Z][a-zA-Z0-9_]{3,31})$", line)
        if m:
            cand = m.group(1)
            if cand.lower() not in {"user", "bot", "none", "null", "false", "true", "info", "telegram"}:
                return cand

    return None

