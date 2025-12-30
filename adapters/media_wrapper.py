from typing import Dict, Any, Optional
from dataclasses import dataclass
import base64


@dataclass
class MediaWrapper:
    original: Any
    url: str
    thumbnail_b64: Optional[str] = None

    def __getattr__(self, name):
        return getattr(self.original, name)

    def to_properties(self) -> Dict[str, Any]:
        props = {}
        for name, value in vars(self.original).items():
            if name in ("_client", "thumbs"):
                continue
            if name == "duration" and value is not None:
                value = round(value)
            props[name] = value
        return props

    async def encode_thumbnail(self, app) -> None:
        if not getattr(self.original, "thumbs", None):
            self.thumbnail_b64 = None
            return

        file = await app.download_media(self.original.thumbs[0], in_memory=True)
        if not file:
            self.thumbnail_b64 = None
            return

        self.thumbnail_b64 = base64.b64encode(file.getbuffer()).decode()
