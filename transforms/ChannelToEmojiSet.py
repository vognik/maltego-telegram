"""
Transform: Channel to Emoji Sets
Extracts all custom emoji sets used in a channel with MTProto thumbnails.
100% MTProto, zero bot_token, zero Bot API.
"""

import asyncio
from typing import Dict, List, Set, Tuple
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.enums import MessageEntityType

from extensions import registry
from client import run_telegram, get_client
from settings import LIMIT, CONCURRENCY
from utils import safe_get_identifier, normalize_identifier, message_is_forwarded_from_another_chat, get_custom_emoji_thumbnail_b64


async def collect_channel_emojis(identifier: str) -> List[Tuple[str, int]]:
    """
    Collect custom emoji IDs from message text, captions, and chat reactions.
    Returns list of unique (set_name, sample_emoji_id).
    """
    client = get_client()
    clean_id = normalize_identifier(identifier)
    emoji_ids: Set[int] = set()

    # 1. Reactions
    try:
        chat = await client.get_chat(clean_id)
        if getattr(chat, "available_reactions", None) and chat.available_reactions.reactions:
            for r in chat.available_reactions.reactions:
                if getattr(r, "custom_emoji_id", None):
                    emoji_ids.add(r.custom_emoji_id)
    except Exception:
        pass

    # 2. Chat history messages
    async for message in client.get_chat_history(clean_id, limit=LIMIT):
        if message_is_forwarded_from_another_chat(message, clean_id):
            continue

        entities = (message.entities or []) + (message.caption_entities or [])
        for ent in entities:
            if ent.type == MessageEntityType.CUSTOM_EMOJI and getattr(ent, "custom_emoji_id", None):
                emoji_ids.add(ent.custom_emoji_id)

    if not emoji_ids:
        return []

    # 3. Batch fetch emoji metadata via MTProto
    batch_size = 150
    emoji_id_list = list(emoji_ids)
    unique_sets: Dict[str, int] = {}

    for i in range(0, len(emoji_id_list), batch_size):
        batch = emoji_id_list[i : i + batch_size]
        try:
            stickers = await client.get_custom_emoji_stickers(custom_emoji_ids=batch)
            for sticker in stickers:
                if sticker.set_name and sticker.set_name not in unique_sets:
                    unique_sets[sticker.set_name] = sticker.custom_emoji_id
        except Exception:
            pass

    return list(unique_sets.items())


async def fetch_emoji_sets_with_thumbs(identifier: str) -> List[Tuple[str, str]]:
    client = get_client()
    emoji_sets = await collect_channel_emojis(identifier)
    results = []

    sem = asyncio.Semaphore(CONCURRENCY)

    async def _fetch_thumb(set_name: str, emoji_id: int):
        async with sem:
            thumb_b64 = await get_custom_emoji_thumbnail_b64(client, emoji_id)
            return set_name, thumb_b64

    tasks = [_fetch_thumb(name, eid) for name, eid in emoji_sets]
    if tasks:
        results = await asyncio.gather(*tasks)

    return results


@registry.register_transform(
    display_name="To Emoji Sets",
    input_entity="interlinked.telegram.Channel",
    description="Extracts custom emoji packs used in a Telegram channel with previews",
    output_entities=["interlinked.telegram.StickerSet"],
)
class ChannelToEmojiSet(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = safe_get_identifier(request, "properties.channel")
        if not identifier:
            response.addUIMessage("No channel specified", messageType="PartialError")
            return

        try:
            sets_with_thumbs = run_telegram(fetch_emoji_sets_with_thumbs(identifier))
            for set_name, thumb_b64 in sets_with_thumbs:
                entity = response.addEntity("interlinked.telegram.StickerSet", value=set_name)
                entity.addProperty("properties.title", value=set_name)
                entity.addProperty("properties.short_name", value=set_name)
                if thumb_b64:
                    entity.addProperty("base64", value=thumb_b64)
                entity.setLinkColor("0xFFAEC9")
                entity.setLinkThickness(2)
        except Exception as e:
            response.addUIMessage(f"Error extracting emoji sets: {e}", messageType="PartialError")
