"""
Transform: Channel to Forwarded Channels
Finds other channels whose posts were forwarded into this channel.
"""

import asyncio
from typing import Dict, List, Tuple
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.types import Chat

from extensions import registry
from client import run_telegram, get_client
from settings import LIMIT, CONCURRENCY
from utils import safe_get_identifier, normalize_identifier, message_is_forwarded_from_another_chat, download_avatar_b64


async def fetch_forwarded_channels(identifier: str) -> List[Tuple[Chat, str]]:
    client = get_client()
    clean_id = normalize_identifier(identifier)
    unique_chats: Dict[int, Chat] = {}

    async for message in client.get_chat_history(clean_id, limit=LIMIT):
        if not message_is_forwarded_from_another_chat(message, clean_id):
            continue

        fwd_chat = message.forward_from_chat
        if fwd_chat and fwd_chat.id not in unique_chats:
            unique_chats[fwd_chat.id] = fwd_chat

    chats = list(unique_chats.values())
    sem = asyncio.Semaphore(CONCURRENCY)

    async def _resolve_avatar(c: Chat):
        async with sem:
            b64 = await download_avatar_b64(client, c)
            return c, b64

    results = []
    if chats:
        results = await asyncio.gather(*(_resolve_avatar(c) for c in chats))

    return results


@registry.register_transform(
    display_name="To Forwarded Channels",
    input_entity="interlinked.telegram.Channel",
    description="Identifies channels whose posts have been forwarded into this channel",
    output_entities=["interlinked.telegram.Channel"],
)
class ChannelToForwardedChannels(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = safe_get_identifier(request, "properties.channel")
        if not identifier:
            response.addUIMessage("No channel specified", messageType="PartialError")
            return

        try:
            channels_with_avatars = run_telegram(fetch_forwarded_channels(identifier))
            for chat, avatar_b64 in channels_with_avatars:
                identity = chat.username or str(chat.id)
                entity = response.addEntity("interlinked.telegram.Channel", value=identity)
                entity.addProperty("properties.id", value=str(chat.id))
                if chat.title:
                    entity.addProperty("properties.title", value=chat.title)
                if chat.username:
                    entity.addProperty("properties.username", value=chat.username)
                if avatar_b64:
                    entity.addProperty("base64", value=avatar_b64)
                entity.setLinkThickness(2)
        except Exception as e:
            response.addUIMessage(f"Error fetching forwarded channels: {e}", messageType="PartialError")
