"""
Unit tests for MediaWrapper adapter.
"""

from dataclasses import dataclass
from adapters.media_wrapper import MediaWrapper


@dataclass
class DummyMedia:
    file_id: str = "test_file_id_123"
    duration: float = 45.7
    width: int = 1920
    height: int = 1080
    _client: str = "hidden_client"


def test_media_wrapper_properties():
    dummy = DummyMedia()
    wrapper = MediaWrapper(
        original=dummy,
        url="https://t.me/test/1",
        description="A" * 200,  # Should be truncated to MAX_DESCRIPTION_LEN (120)
    )

    assert len(wrapper.description) == 120
    assert wrapper.file_id == "test_file_id_123"

    props = wrapper.to_properties()
    assert props["duration"] == 46  # round(45.7)
    assert props["width"] == 1920
    assert props["height"] == 1080
    assert "_client" not in props
