"""
Transform: Compressed Image to OS
Identifies the operating system and device type based on Telegram's JPEG compression byte signatures.
Optimized with precompiled binary byte patterns for maximum speed.
"""

import base64
from dataclasses import dataclass
from typing import Optional, Tuple
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform

from extensions import registry
from utils import safe_get_property

SMARTPHONE = "maltego.Smartphone"
DESKTOP = "maltego.DesktopComputer"


@dataclass(frozen=True)
class DeviceSignature:
    prefix_bytes: bytes
    os_name: str
    device_type: str


# Precompiled binary signatures (replaces expensive hex string manipulation)
SIGNATURES: Tuple[DeviceSignature, ...] = (
    DeviceSignature(bytes.fromhex("FFD8FFE000104A46494600010100000100010000FFDB004300090607"), "iOS", SMARTPHONE),
    DeviceSignature(bytes.fromhex("FFD8FFE000104A46494600010101004800480000FFE201D84943435F50524F46494C45"), "Android", SMARTPHONE),
    DeviceSignature(bytes.fromhex("FFD8FFE000104A464946000101010078"), "Desktop Windows/Linux", DESKTOP),
    DeviceSignature(bytes.fromhex("FFD8FFE000104A464946000101010060"), "Desktop (Alternative)", DESKTOP),
    DeviceSignature(bytes.fromhex("FFD8FFE000104A46494600010101004800480000FFE201DB"), "Desktop (ICC Profile)", DESKTOP),
    DeviceSignature(bytes.fromhex("FFD8FFE000104A46494600010101004800480000FFDB00"), "iOS, Desktop", DESKTOP),
    DeviceSignature(bytes.fromhex("FFD8FFE000104A46494600010101004800480000FFE202"), "Android (Legacy)", SMARTPHONE),
    DeviceSignature(bytes.fromhex("FFD8FFE000104A4649460001010101"), "Desktop macOS", DESKTOP),
    DeviceSignature(bytes.fromhex("FFD8FFE000104A46494600010101009000900000FFE201DB"), "Desktop macOS (High-DPI)", DESKTOP),
    DeviceSignature(bytes.fromhex("FFD8FFE000104A46494600010100000100010000FFDB004300090606"), "macOS (Preview)", DESKTOP),
    DeviceSignature(bytes.fromhex("FFD8FFE000104A46494600010100000100010000FFDB004300080606"), "macOS (Export)", DESKTOP),
    DeviceSignature(bytes.fromhex("FFD8FFE000104A46494600010101009000900000FFDB004300"), "macOS (Retina)", DESKTOP),
)


def identify_device(image_bytes: bytes) -> Optional[DeviceSignature]:
    """Match image header bytes against device compression signatures."""
    for sig in SIGNATURES:
        if image_bytes.startswith(sig.prefix_bytes):
            return sig
    return None


@registry.register_transform(
    display_name="To OS",
    input_entity="interlinked.telegram.CompressedImage",
    description="Identifies the sender operating system and device based on Telegram image compression pattern",
    output_entities=[SMARTPHONE, DESKTOP],
)
class CompressedImageToOS(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        image_base64 = safe_get_property(request, "base64")
        if not image_base64:
            response.addUIMessage("No base64 image data found", messageType="PartialError")
            return

        try:
            image_bytes = base64.b64decode(image_base64)
            match = identify_device(image_bytes)
            if match:
                entity = response.addEntity(match.device_type, value=match.os_name)
                entity.addProperty("properties.os", value=match.os_name)
                entity.addProperty("properties.device", value=match.device_type)
            else:
                response.addUIMessage("Unknown compression signature", messageType="Inform")
        except Exception as e:
            response.addUIMessage(f"Error analyzing image compression: {e}", messageType="PartialError")