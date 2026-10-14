"""
Transform: Channel to Videos
Extracts video files from a Telegram channel with MTProto thumbnails and metadata.
"""

import asyncio
from dataclasses import dataclass
from typing import List
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.types import Video

from extensions import registry
from client import run_telegram, get_client
from settings import LIMIT, CONCURRENCY
from adapters.media_wrapper import MediaWrapper
from utils import safe_get_identifier, normalize_identifier, message_is_forwarded_from_another_chat


@dataclass
class VideoWrapper(MediaWrapper):
    original: Video

    @property
    def file_name(self) -> str:
        return getattr(self.original, "file_name", "") or f"video_{self.original.file_unique_id}.mp4"


async def fetch_videos(identifier: str) -> List[VideoWrapper]:
    client = get_client()
    clean_id = normalize_identifier(identifier)
    videos: List[VideoWrapper] = []

    async for message in client.get_chat_history(clean_id, limit=LIMIT):
        if message.video and not message_is_forwarded_from_another_chat(message, clean_id):
            url = f"https://t.me/{clean_id}/{message.id}"
            description = message.caption or message.video.file_name or f"Video #{message.id}"
            video = VideoWrapper(original=message.video, url=url, description=description)
            videos.append(video)

    if videos:
        sem = asyncio.Semaphore(CONCURRENCY)
        await asyncio.gather(*(v.encode_thumbnail(client, sem) for v in videos))

    return videos


@registry.register_transform(
    display_name="To Videos",
    input_entity="interlinked.telegram.Channel",
    description="Finds video files in a Telegram channel with thumbnails and duration details",
    output_entities=["maltego.Video"],
)
class ChannelToVideos(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = safe_get_identifier(request, "properties.channel")
        if not identifier:
            response.addUIMessage("No channel specified", messageType="PartialError")
            return

        try:
            videos = run_telegram(fetch_videos(identifier))
            for video in videos:
                entity = response.addEntity("maltego.Video", value=video.url)
                entity.addProperty("name", value=video.file_name)
                if video.thumbnail_b64:
                    entity.addProperty("base64", value=video.thumbnail_b64)

                for k, v in video.to_properties().items():
                    entity.addProperty(f"properties.{k}", value=str(v))
        except Exception as e:
            response.addUIMessage(f"Error fetching videos: {e}", messageType="PartialError")
