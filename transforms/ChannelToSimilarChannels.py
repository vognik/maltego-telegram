"""
Transform: Channel to Similar Channels
Identifies similar public channels with overlapping subscriber bases.
100% MTProto, zero web scraping.
"""

import asyncio
from typing import List, Tuple
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.types import Chat

from extensions import registry
from client import run_telegram, get_client
from settings import CONCURRENCY
from utils import safe_get_identifier, normalize_identifier, download_avatar_b64


async def fetch_similar_channels(identifier: str) -> List[Tuple[Chat, str]]:
    client = get_client()
    clean_id = normalize_identifier(identifier)

    similar_chats = await client.get_similar_channels(clean_id)
    if not similar_chats:
        return []

    sem = asyncio.Semaphore(CONCURRENCY)

    async def _fetch_avatar(c: Chat):
        async with sem:
            b64 = await download_avatar_b64(client, c)
            return c, b64

    results = await asyncio.gather(*(_fetch_avatar(c) for c in similar_chats))
    return results


@registry.register_transform(
    display_name="To Similar Channels",
    input_entity="interlinked.telegram.Channel",
    description="Identifies similar channels by analyzing overlapping subscriber bases via MTProto",
    output_entities=["interlinked.telegram.Channel"],
)
class ChannelToSimilarChannels(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = safe_get_identifier(request, "properties.channel")
        if not identifier:
            response.addUIMessage("No channel specified", messageType="PartialError")
            return

        try:
            channels_with_avatars = run_telegram(fetch_similar_channels(identifier))
            for chat, avatar_b64 in channels_with_avatars:
                username = chat.username or (chat.usernames[0].username if getattr(chat, "usernames", None) else "")
                identity = username or str(chat.id)

                entity = response.addEntity("interlinked.telegram.Channel", value=identity)
                entity.addProperty("properties.id", value=str(chat.id))
                if chat.title:
                    entity.addProperty("properties.title", value=chat.title)
                if username:
                    entity.addProperty("properties.username", value=username)
                if avatar_b64:
                    entity.addProperty("base64", value=avatar_b64)
                if getattr(chat, "members_count", None):
                    entity.addProperty("properties.members_count", value=str(chat.members_count))

                entity.setLinkThickness(2)
        except Exception as e:
            response.addUIMessage(f"Error fetching similar channels: {e}", messageType="PartialError")
