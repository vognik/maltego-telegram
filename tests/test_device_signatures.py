"""
Unit tests for JPEG image compression signatures in CompressedImageToOS.
"""

from transforms.CompressedImageToOS import identify_device, SMARTPHONE, DESKTOP


def test_identify_ios_device():
    # iOS signature
    header = bytes.fromhex("FFD8FFE000104A46494600010100000100010000FFDB004300090607") + b"\x00" * 20
    sig = identify_device(header)
    assert sig is not None
    assert sig.os_name == "iOS"
    assert sig.device_type == SMARTPHONE


def test_identify_android_device():
    # Android signature
    header = bytes.fromhex("FFD8FFE000104A46494600010101004800480000FFE201D84943435F50524F46494C45") + b"\x00" * 20
    sig = identify_device(header)
    assert sig is not None
    assert sig.os_name == "Android"
    assert sig.device_type == SMARTPHONE


def test_identify_desktop_device():
    # Desktop signature
    header = bytes.fromhex("FFD8FFE000104A464946000101010078") + b"\x00" * 20
    sig = identify_device(header)
    assert sig is not None
    assert sig.device_type == DESKTOP


def test_unknown_signature():
    header = b"\x00" * 50
    sig = identify_device(header)
    assert sig is None
