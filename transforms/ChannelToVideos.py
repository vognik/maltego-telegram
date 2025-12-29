from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform

import io
import base64
from typing import Dict
from dataclasses import dataclass
from pyrogram.types import Video

from settings import app, loop, limit
from extensions import registry
from utils import message_is_forwarded_from_another_chat, fetch_web_info


@dataclass
class Video:
    original: Video
    url: str
    thumbnail_b64: str | None = None

    def __getattr__(self, name):
        return getattr(self.original, name)

    def to_properties(self) -> Dict[str, object]:
        props = {}
        for name, value in vars(self.original).items():
            if name in ("_client", "thumbs"):
                continue
            if name == "duration" and value is not None:
                value = round(value)
            props[name] = value
        return props


async def encode_thumbnail(file_id):
    file = await app.download_media(file_id, in_memory=True)
    if not file:
        return None

    return base64.b64encode(file.getbuffer()).decode()


async def fetch_videos(username):
    videos = []
    
    async with app:
        async for message in app.get_chat_history(username, limit=limit):
            if message.video and not message_is_forwarded_from_another_chat(message, username):
                video = Video(original=message.video, url=f"https://t.me/{username}/{message.id}")
                video.thumbnail_b64 = await encode_thumbnail(video.thumbs[0])
                videos.append(video)

    return videos


@registry.register_transform(display_name="To Videos", input_entity="interlinked.telegram.Channel",
                             description="This Transform finds videos in a Telegram channel and provides details like filename, duration, and thumbnail for each video.",
                             output_entities=["maltego.Video"])
class ChannelToVideos(DiscoverableTransform):

    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = request.getProperty("properties.channel")
        videos = loop.run_until_complete(fetch_videos(username))

        for video in videos:
            entity = response.addEntity("maltego.Video", value=video.url)
            entity.addProperty("base64", value=video.thumbnail_b64)
            entity.addProperty("name", value=video.file_name)
            for name, value in video.to_properties().items():
                entity.addProperty(name, value=value)