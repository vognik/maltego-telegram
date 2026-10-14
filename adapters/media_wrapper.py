"""
Adapter wrapper for Telegram media items (photos, videos, video notes, documents).
Provides memory-efficient MTProto thumbnail and file downloads with concurrency support.
"""

import asyncio
import base64
from dataclasses import dataclass
from typing import Any, Dict, Optional
from pyrogram import Client

MAX_DESCRIPTION_LEN = 120
EXCLUDE_ATTRS = {"_client", "thumbs", "raw", "file_ref", "file_reference"}


@dataclass
class MediaWrapper:
    original: Any
    url: str
    description: Optional[str] = None
    thumbnail_b64: Optional[str] = None
    file_bytes: Optional[bytes] = None

    def __post_init__(self):
        if self.description:
            self.description = self.description[:MAX_DESCRIPTION_LEN]

    def __getattr__(self, name: str) -> Any:
        return getattr(self.original, name)

    def to_properties(self) -> Dict[str, Any]:
        """Extract clean entity properties for Maltego without leaking internal state."""
        props: Dict[str, Any] = {}
        source = vars(self.original) if hasattr(self.original, "__dict__") else {}
        for name, value in source.items():
            if name in EXCLUDE_ATTRS or name.startswith("_"):
                continue
            if name == "duration" and value is not None:
                value = round(value)
            if value is not None:
                props[name] = value
        return props

    async def download_file(self, client: Client, semaphore: Optional[asyncio.Semaphore] = None) -> Optional[bytes]:
        """Download full media file into memory via MTProto."""
        if self.file_bytes is not None:
            return self.file_bytes

        async def _download():
            file = await client.download_media(self.original, in_memory=True)
            if file and hasattr(file, "getbuffer"):
                self.file_bytes = bytes(file.getbuffer())
            return self.file_bytes

        if semaphore:
            async with semaphore:
                return await _download()
        return await _download()

    async def encode_thumbnail(
        self, client: Client, semaphore: Optional[asyncio.Semaphore] = None
    ) -> Optional[str]:
        """Download small media thumbnail and encode to base64 via MTProto."""
        if self.thumbnail_b64 is not None:
            return self.thumbnail_b64

        thumbs = getattr(self.original, "thumbs", None)
        target = thumbs[0] if thumbs else self.original

        if not target:
            return None

        async def _encode():
            try:
                file = await client.download_media(target, in_memory=True)
                if file and hasattr(file, "getbuffer"):
                    self.thumbnail_b64 = base64.b64encode(bytes(file.getbuffer())).decode("utf-8")
                    return self.thumbnail_b64
            except Exception:
                pass
            return None

        if semaphore:
            async with semaphore:
                return await _encode()
        return await _encode()
