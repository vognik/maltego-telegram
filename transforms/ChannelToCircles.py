from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from extensions import registry
from settings import app, loop, limit
from pyrogram.types import VideoNote
from dataclasses import dataclass
from adapters.media_wrapper import MediaWrapper


@dataclass
class VideoNoteWrapper(MediaWrapper):
    original: VideoNote


async def fetch_circles_from_channel(username):
    circles = []

    async with app:
        async for message in app.get_chat_history(username, limit=limit):
            if not message.video_note:
                continue

            video_note = VideoNoteWrapper(
                original=message.video_note, url=f"https://t.me/{username}/{message.id}"
            )

            await video_note.encode_thumbnail(app)

            circles.append(video_note)

    return circles


@registry.register_transform(
    display_name="To Circles",
    input_entity="interlinked.telegram.Channel",
    description="This Transform finds circles in a Telegram channel and provides details like size, thumbnail, and more for each circle.",
    output_entities=["maltego.Video"],
)
class ChannelToCircles(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = request.getProperty("properties.channel")
        circles = loop.run_until_complete(fetch_circles_from_channel(username))

        for circle in circles:
            entity = response.addEntity("maltego.Video", value=circle.url)
            entity.addProperty("base64", value=circle.thumbnail_b64)
            entity.addProperty("name", value=circle.url)

            for name, value in circle.to_properties().items():
                entity.addProperty(name, value=value)
