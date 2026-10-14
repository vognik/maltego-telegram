"""
Transform: Channel to RAW Photos
Extracts uncompressed raw photos (documents) from a Telegram channel and parses EXIF metadata.
"""

import asyncio
from dataclasses import dataclass
import io
from typing import Any, Dict, List, Optional
from PIL import Image, ExifTags
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.types import Document

from extensions import registry
from client import run_telegram, get_client
from settings import LIMIT, CONCURRENCY
from adapters.media_wrapper import MediaWrapper
from utils import safe_get_identifier, normalize_identifier, message_is_forwarded_from_another_chat


def flatten_dict(d: Dict[str, Any], prefix: str = "") -> List[tuple]:
    """Recursively flatten nested dictionary into dot-separated keys."""
    items = []
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict) and v:
            items.extend(flatten_dict(v, key))
        else:
            items.append((key, str(v)))
    return items


class ExifExtractor:
    """Parses EXIF and GPS tags from image bytes."""

    def __init__(self):
        self.ifd_lookup = {ifd.value: ifd.name for ifd in ExifTags.IFD}

    def extract(self, data: bytes) -> Dict[str, Any]:
        try:
            with Image.open(io.BytesIO(data)) as img:
                exif = img.getexif()
                if not exif:
                    return {}
                return self._parse_ifds(exif)
        except Exception:
            return {}

    def _parse_ifds(self, exif) -> Dict[str, Any]:
        result = {}
        for ifd_code, ifd_name in self.ifd_lookup.items():
            if ifd_code not in exif:
                continue
            ifd_data = exif.get_ifd(ifd_code)
            parsed = {
                self._resolve_tag(tag_id): str(val)
                for tag_id, val in ifd_data.items()
            }
            if parsed:
                result[ifd_name] = parsed
        return result

    @staticmethod
    def _resolve_tag(tag_id: int) -> str:
        return str(ExifTags.GPSTAGS.get(tag_id) or ExifTags.TAGS.get(tag_id) or tag_id)


@dataclass
class PhotoWrapper(MediaWrapper):
    original: Document
    metadata: Optional[Dict[str, Any]] = None

    @property
    def file_name(self) -> str:
        return getattr(self.original, "file_name", "") or "raw_photo.jpg"

    async def extract_metadata(self, client, sem: asyncio.Semaphore):
        await self.download_file(client, sem)
        if self.file_bytes:
            extractor = ExifExtractor()
            self.metadata = extractor.extract(self.file_bytes)
        await self.encode_thumbnail(client, sem)


async def fetch_raw_photos(identifier: str) -> List[PhotoWrapper]:
    client = get_client()
    clean_id = normalize_identifier(identifier)
    photos: List[PhotoWrapper] = []

    async for message in client.get_chat_history(clean_id, limit=LIMIT):
        doc = message.document
        if not doc or not doc.mime_type or not doc.mime_type.startswith("image/"):
            continue
        if message_is_forwarded_from_another_chat(message, clean_id):
            continue

        url = f"https://t.me/{clean_id}/{message.id}"
        photo = PhotoWrapper(original=doc, url=url, description=doc.file_name or f"Raw Photo #{message.id}")
        photos.append(photo)

    if photos:
        sem = asyncio.Semaphore(CONCURRENCY)
        await asyncio.gather(*(p.extract_metadata(client, sem) for p in photos))

    return photos


@registry.register_transform(
    display_name="To RAW Photos",
    input_entity="interlinked.telegram.Channel",
    description="Finds raw uncompressed photos in a Telegram channel and extracts EXIF metadata",
    output_entities=["maltego.Image"],
)
class ChannelToRawPhotos(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = safe_get_identifier(request, "properties.channel")
        if not identifier:
            response.addUIMessage("No channel specified", messageType="PartialError")
            return

        try:
            photos = run_telegram(fetch_raw_photos(identifier))
            for photo in photos:
                entity = response.addEntity("maltego.Image", value=photo.file_name)
                entity.addProperty("url", value=photo.url)
                if photo.thumbnail_b64:
                    entity.addProperty("base64", value=photo.thumbnail_b64)

                for k, v in photo.to_properties().items():
                    entity.addProperty(f"properties.{k}", value=str(v))

                if photo.metadata:
                    for tag_key, tag_val in flatten_dict(photo.metadata):
                        entity.addProperty(f"exif.{tag_key}", value=tag_val)

        except Exception as e:
            response.addUIMessage(f"Error extracting raw photos: {e}", messageType="PartialError")
