"""
Transform: Channel to Circles (Video Notes)
Extracts video notes (telescope circles) with MTProto thumbnails and metadata.
"""

import asyncio
from typing import List
from dataclasses import dataclass
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.types import VideoNote

from extensions import registry
from client import run_telegram, get_client
from settings import LIMIT, CONCURRENCY
from adapters.media_wrapper import MediaWrapper
from utils import safe_get_identifier, normalize_identifier


@dataclass
class VideoNoteWrapper(MediaWrapper):
    original: VideoNote


async def fetch_circles(identifier: str) -> List[VideoNoteWrapper]:
    client = get_client()
    clean_id = normalize_identifier(identifier)
    circles: List[VideoNoteWrapper] = []

    async for message in client.get_chat_history(clean_id, limit=LIMIT):
        if message.video_note:
            wrapper = VideoNoteWrapper(
                original=message.video_note,
                url=f"https://t.me/{clean_id}/{message.id}",
                description=f"Circle #{message.id}",
            )
            circles.append(wrapper)

    # Concurrently encode thumbnails via MTProto
    if circles:
        sem = asyncio.Semaphore(CONCURRENCY)
        await asyncio.gather(*(c.encode_thumbnail(client, sem) for c in circles))

    return circles


@registry.register_transform(
    display_name="To Circles",
    input_entity="interlinked.telegram.Channel",
    description="Finds video notes (circles) in a Telegram channel with thumbnail previews",
    output_entities=["maltego.Video"],
)
class ChannelToCircles(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = safe_get_identifier(request, "properties.channel")
        if not identifier:
            response.addUIMessage("No channel specified", messageType="PartialError")
            return

        try:
            circles = run_telegram(fetch_circles(identifier))
            for circle in circles:
                entity = response.addEntity("maltego.Video", value=circle.url)
                if circle.thumbnail_b64:
                    entity.addProperty("base64", value=circle.thumbnail_b64)
                entity.addProperty("name", value=circle.url)
                for prop_name, prop_val in circle.to_properties().items():
                    entity.addProperty(f"properties.{prop_name}", value=str(prop_val))
        except Exception as e:
            response.addUIMessage(f"Error fetching circles: {e}", messageType="PartialError")
