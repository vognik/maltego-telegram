import io
from dataclasses import dataclass
from PIL import Image, ExifTags
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.types import Document
from settings import app, loop, limit
from extensions import registry
from utils import message_is_forwarded_from_another_chat
from adapters.media_wrapper import MediaWrapper


def flatten_deepest(d, parent_key=""):
    items = []
    for key, value in d.items():
        full_key = f"{parent_key}.{key}" if parent_key else str(key)
        if isinstance(value, dict) and value:
            items.extend(flatten_deepest(value, full_key))
        else:
            items.append((full_key, value))
    return items


class ExifExtractor:
    def __init__(self):
        self.ifd_lookup = {ifd.value: ifd.name for ifd in ExifTags.IFD}

    def extract(self, data):
        with Image.open(io.BytesIO(data)) as image:
            exif = image.getexif()
            if not exif:
                return {}
            return self._parse_ifds(exif)

    def _parse_ifds(self, exif):
        result = {}
        for ifd_code, ifd_name in self.ifd_lookup.items():
            if ifd_code not in exif:
                continue
            ifd_data = exif.get_ifd(ifd_code)
            parsed = {
                self._resolve_tag_name(tag_id): value
                for tag_id, value in ifd_data.items()
            }
            if parsed:
                result[ifd_name] = parsed
        return result

    @staticmethod
    def _resolve_tag_name(tag_id):
        return ExifTags.GPSTAGS.get(tag_id) or ExifTags.TAGS.get(tag_id) or tag_id


@dataclass
class PhotoWrapper(MediaWrapper):
    original: Document
    file_bytes: bytes = None
    metadata: dict = None

    @property
    def file_name(self):
        return getattr(self.original, "file_name", None)

    async def download_file(self):
        if self.file_bytes is None:
            file = await app.download_media(self.original, in_memory=True)
            if file:
                self.file_bytes = bytes(file.getbuffer())
        return self.file_bytes

    async def extract_metadata(self):
        if self.file_bytes is None:
            await self.download_file()
        if self.file_bytes:
            extractor = ExifExtractor()
            self.metadata = extractor.extract(self.file_bytes)


async def fetch_photos_from_channel(username):
    photos = []

    async with app:
        async for message in app.get_chat_history(username, limit=limit):
            if not message.document:
                continue
            if message_is_forwarded_from_another_chat(message, username):
                continue
            if not message.document.mime_type.startswith("image/"):
                continue

            photo = PhotoWrapper(
                original=message.document, url=f"https://t.me/{username}/{message.id}"
            )

            await photo.download_file()
            await photo.extract_metadata()
            await photo.encode_thumbnail()

            photos.append(photo)

    return photos


@registry.register_transform(
    display_name="To RAW Photos",
    input_entity="interlinked.telegram.Channel",
    description="This Transform finds raw photos in a Telegram channel and provides details like filename, thumbnail, and more for each photo.",
    output_entities=["maltego.Image"],
)
class ChannelToRawPhotos(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = request.getProperty("properties.channel")
        photos = loop.run_until_complete(fetch_photos_from_channel(username))
        for photo in photos:
            entity = response.addEntity("maltego.Image", value=photo.file_name)
            entity.addProperty("base64", value=photo.thumbnail_b64)
            entity.addProperty("url", value=photo.url)
            for name, value in photo.to_properties().items():
                entity.addProperty(name, value=value)
            flattened_metadata = flatten_deepest(photo.metadata)
            for name, value in flattened_metadata:
                entity.addProperty(name, value=value)
