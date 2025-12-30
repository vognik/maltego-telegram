from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform

from dataclasses import dataclass
from pyrogram.types import Video

from settings import app, loop, limit
from extensions import registry
from utils import message_is_forwarded_from_another_chat

from adapters.media_wrapper import MediaWrapper


@dataclass
class VideoWrapper(MediaWrapper):
    original: Video


async def fetch_videos(username):
    videos = []

    async with app:
        async for message in app.get_chat_history(username, limit=limit):
            if message.video and not message_is_forwarded_from_another_chat(
                message, username
            ):
                video = VideoWrapper(
                    original=message.video, url=f"https://t.me/{username}/{message.id}"
                )
                await video.encode_thumbnail(app)
                videos.append(video)

    return videos


@registry.register_transform(
    display_name="To Videos",
    input_entity="interlinked.telegram.Channel",
    description="This Transform finds videos in a Telegram channel and provides details like filename, duration, and thumbnail for each video.",
    output_entities=["maltego.Video"],
)
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
