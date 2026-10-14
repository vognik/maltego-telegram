"""
Transform: Channel to Sticker Sets
Extracts all sticker sets used in a Telegram channel with MTProto thumbnails.
100% MTProto, zero bot_token, zero Bot API.
"""

import asyncio
from typing import Dict, List, Tuple
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.types import Sticker

from extensions import registry
from client import run_telegram, get_client
from settings import LIMIT, CONCURRENCY
from utils import safe_get_identifier, normalize_identifier, get_sticker_set_thumbnail_b64


async def fetch_sticker_sets(identifier: str) -> List[Tuple[str, str]]:
    client = get_client()
    clean_id = normalize_identifier(identifier)
    unique_sets: Dict[str, Sticker] = {}

    async for message in client.get_chat_history(clean_id, limit=LIMIT):
        sticker = message.sticker
        if sticker and sticker.set_name and sticker.set_name not in unique_sets:
            unique_sets[sticker.set_name] = sticker

    if not unique_sets:
        return []

    sem = asyncio.Semaphore(CONCURRENCY)

    async def _fetch_thumb(set_name: str, sticker: Sticker):
        async with sem:
            # First try downloading from the sticker instance already in hand
            thumb_target = sticker.thumbs[0] if getattr(sticker, "thumbs", None) else sticker
            try:
                data = await client.download_media(thumb_target, in_memory=True)
                if data and hasattr(data, "getbuffer"):
                    import base64
                    return set_name, base64.b64encode(bytes(data.getbuffer())).decode("utf-8")
            except Exception:
                pass

            # Fallback to GetStickerSet
            b64 = await get_sticker_set_thumbnail_b64(client, set_name)
            return set_name, b64

    tasks = [_fetch_thumb(name, st) for name, st in unique_sets.items()]
    results = await asyncio.gather(*tasks)
    return results


@registry.register_transform(
    display_name="To Sticker Sets",
    input_entity="interlinked.telegram.Channel",
    description="Extracts all sticker sets used in a Telegram channel with previews",
    output_entities=["interlinked.telegram.StickerSet"],
)
class ChannelToStickerSet(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = safe_get_identifier(request, "properties.channel")
        if not identifier:
            response.addUIMessage("No channel specified", messageType="PartialError")
            return

        try:
            sticker_sets = run_telegram(fetch_sticker_sets(identifier))
            for set_name, thumb_b64 in sticker_sets:
                entity = response.addEntity("interlinked.telegram.StickerSet", value=set_name)
                entity.addProperty("properties.title", value=set_name)
                entity.addProperty("properties.short_name", value=set_name)
                if thumb_b64:
                    entity.addProperty("base64", value=thumb_b64)
                entity.setLinkColor("0x99D9EA")
                entity.setLinkThickness(2)
        except Exception as e:
            response.addUIMessage(f"Error fetching sticker sets: {e}", messageType="PartialError")
