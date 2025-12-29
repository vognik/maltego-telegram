from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform

import base64
from typing import Dict
from dataclasses import dataclass
from pyrogram.types import Document

from settings import app, loop, limit
from extensions import registry
from utils import message_is_forwarded_from_another_chat, fetch_web_info


@dataclass
class Photo:
    original: Document
    url: str
    thumbnail_b64: str | None = None

    def __getattr__(self, name):
        return getattr(self.original, name)

    def to_properties(self) -> Dict[str, object]:
        props = {}
        for name, value in vars(self.original).items():
            if name in ("_client", "thumbs"):
                continue
            props[name] = value
        return props

    async def encode_thumbnail(self, app) -> None:
        if not self.thumbs:
            self.thumbnail_b64 = None
            return

        file = await app.download_media(self.thumbs[0], in_memory=True)
        if not file:
            self.thumbnail_b64 = None
            return

        self.thumbnail_b64 = base64.b64encode(file.getbuffer()).decode()


async def fetch_raw_photos(username):
    photos = []
    
    async with app:
        async for message in app.get_chat_history(username, limit=limit):
            if not message.document or message_is_forwarded_from_another_chat(message, username):
                continue
            if message.document.mime_type.startswith('image/'):
                photo = Photo(original=message.document, url=f"https://t.me/{username}/{message.id}")
                await photo.encode_thumbnail(app)
                photos.append(photo)

    return photos


@registry.register_transform(display_name="To RAW Photos", input_entity="interlinked.telegram.Channel",
                             description="This Transform finds raw photos in a Telegram channel and provides details like filename, thumbnail, and more for each photo.",
                             output_entities=["maltego.Image"])
class ChannelToRawPhotos(DiscoverableTransform):

    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = request.getProperty("properties.channel")
        photos = loop.run_until_complete(fetch_raw_photos(username))

        for photo in photos:
            entity = response.addEntity("maltego.Image", value=photo.file_name)
            entity.addProperty("base64", value=photo.thumbnail_b64)
            entity.addProperty("url", value=photo.url)

            for name, value in photo.to_properties().items():
                entity.addProperty(name, value=value)