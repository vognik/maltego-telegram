import io
from dataclasses import dataclass
from PIL import Image, ExifTags
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from settings import app, loop, limit
from extensions import registry
from utils import message_is_forwarded_from_another_chat
from adapters.media_wrapper import MediaWrapper
from pyrogram.enums import MessageMediaType
import base64


async def fetch_images_from_channel(username):
    images = []

    async with app:
        async for message in app.get_chat_history(username, limit=limit):
            if not message.media == MessageMediaType.PHOTO:
                continue
            if message_is_forwarded_from_another_chat(message, username):
                continue

            image = MediaWrapper(
                original=message.photo, url=f"https://t.me/{username}/{message.id}", description=message.caption
            )

            await image.encode_thumbnail(app)

            images.append(image)

    return images


@registry.register_transform(
    display_name="To Compressed Images",
    input_entity="interlinked.telegram.Channel",
    description="This Transform finds compressed images in a Telegram channel",
    output_entities="interlinked.telegram.CompressedImage",
)
class ChannelToCompressedImages(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = request.getProperty("properties.channel")
        images = loop.run_until_complete(fetch_images_from_channel(username))

        for image in images:
            entity = response.addEntity("interlinked.telegram.CompressedImage", value=image.description)
            entity.addProperty("url", value=image.url)
            entity.addProperty("base64", value=image.thumbnail_b64)