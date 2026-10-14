"""
Transform: Channel to Compressed Images
Extracts photo images from a channel with MTProto thumbnails for OS and compression analysis.
"""

import asyncio
from typing import List
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.enums import MessageMediaType

from extensions import registry
from client import run_telegram, get_client
from settings import LIMIT, CONCURRENCY
from adapters.media_wrapper import MediaWrapper
from utils import safe_get_identifier, normalize_identifier, message_is_forwarded_from_another_chat


async def fetch_compressed_images(identifier: str) -> List[MediaWrapper]:
    client = get_client()
    clean_id = normalize_identifier(identifier)
    images: List[MediaWrapper] = []

    async for message in client.get_chat_history(clean_id, limit=LIMIT):
        if message.media != MessageMediaType.PHOTO:
            continue
        if message_is_forwarded_from_another_chat(message, clean_id):
            continue

        url = f"https://t.me/{clean_id}/{message.id}"
        description = message.caption or f"Photo #{message.id}"
        image = MediaWrapper(original=message.photo, url=url, description=description)
        images.append(image)

    if images:
        sem = asyncio.Semaphore(CONCURRENCY)
        await asyncio.gather(*(img.encode_thumbnail(client, sem) for img in images))

    return images


@registry.register_transform(
    display_name="To Compressed Images",
    input_entity="interlinked.telegram.Channel",
    description="Finds compressed images in a Telegram channel for compression analysis",
    output_entities=["interlinked.telegram.CompressedImage"],
)
class ChannelToCompressedImages(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = safe_get_identifier(request, "properties.channel")
        if not identifier:
            response.addUIMessage("No channel specified", messageType="PartialError")
            return

        try:
            images = run_telegram(fetch_compressed_images(identifier))
            for image in images:
                entity = response.addEntity("interlinked.telegram.CompressedImage", value=image.description or image.url)
                entity.addProperty("url", value=image.url)
                if image.thumbnail_b64:
                    entity.addProperty("base64", value=image.thumbnail_b64)
        except Exception as e:
            response.addUIMessage(f"Error fetching images: {e}", messageType="PartialError")