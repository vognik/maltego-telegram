"""
Unit tests for transform registry and offline transform execution.
"""

import base64
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from transforms.CompressedImageToOS import CompressedImageToOS


def test_compressed_image_transform_execution():
    # Construct base64 iOS header
    ios_bytes = bytes.fromhex("FFD8FFE000104A46494600010100000100010000FFDB004300090607") + b"\x00" * 30
    b64 = base64.b64encode(ios_bytes).decode()

    xml = (
        '<MaltegoMessage><MaltegoTransformRequestMessage><Entities><Entity Type="interlinked.telegram.CompressedImage">'
        '<Value>test_img</Value><Weight>100</Weight><AdditionalFields>'
        f'<Field Name="base64">{b64}</Field>'
        '</AdditionalFields></Entity></Entities>'
        '<Limits SoftLimit="100" HardLimit="100"/>'
        '</MaltegoTransformRequestMessage></MaltegoMessage>'
    )

    req = MaltegoMsg(xml)
    resp = MaltegoTransform()

    CompressedImageToOS.create_entities(req, resp)

    assert len(resp.entities) == 1
    entity = resp.entities[0]
    assert entity.entityType == "maltego.Smartphone"
    assert entity.value == "iOS"


def test_compressed_image_missing_base64():
    xml = (
        '<MaltegoMessage><MaltegoTransformRequestMessage><Entities><Entity Type="interlinked.telegram.CompressedImage">'
        '<Value>test_img</Value><Weight>100</Weight></Entity></Entities>'
        '<Limits SoftLimit="100" HardLimit="100"/>'
        '</MaltegoTransformRequestMessage></MaltegoMessage>'
    )

    req = MaltegoMsg(xml)
    resp = MaltegoTransform()

    CompressedImageToOS.create_entities(req, resp)

    assert len(resp.entities) == 0
    assert len(resp.UIMessages) == 1
    assert "No base64" in str(resp.UIMessages[0])
