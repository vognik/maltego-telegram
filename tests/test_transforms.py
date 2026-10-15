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


def test_parse_candidate():
    from transforms.ProfileToIP import parse_candidate

    sdp_srflx = "a=candidate:0 1 UDP 2122252543 93.184.216.34 54321 typ srflx"
    cand = parse_candidate(sdp_srflx)
    assert cand is not None
    assert cand.address == "93.184.216.34"
    assert cand.port == 54321
    assert cand.protocol == "udp"
    assert cand.kind == "srflx"
    assert cand.is_global is True

    sdp_host_private = "candidate:1 1 UDP 2122252543 192.168.1.50 54321 typ host"
    cand_priv = parse_candidate(sdp_host_private)
    assert cand_priv is not None
    assert cand_priv.is_global is False

    sdp_relay = "candidate:2 1 UDP 2122252543 149.154.167.91 54321 typ relay"
    cand_relay = parse_candidate(sdp_relay)
    assert cand_relay is not None
    assert cand_relay.kind == "relay"

    assert parse_candidate("invalid candidate string") is None
    assert parse_candidate(123) is None


def test_candidate_handler():
    import logging
    from transforms.ProfileToIP import CandidateHandler, Candidate

    captured = []
    handler = CandidateHandler(lambda c: captured.append(c))

    log_record = logging.LogRecord(
        name="ntgcalls",
        level=logging.DEBUG,
        pathname="",
        lineno=0,
        msg='processSignalingData: {"@type":"Candidates","candidates":[{"sdpString":"a=candidate:0 1 UDP 2122252543 93.184.216.34 54321 typ srflx"}]}',
        args=(),
        exc_info=None,
    )
    handler.emit(log_record)

    assert len(captured) == 1
    assert captured[0].address == "93.184.216.34"
    assert captured[0].kind == "srflx"


def test_profile_to_ip_missing_identifier():
    from transforms.ProfileToIP import ProfileToIP

    xml = (
        '<MaltegoMessage><MaltegoTransformRequestMessage><Entities><Entity Type="interlinked.telegram.UserProfile">'
        '<Value></Value><Weight>100</Weight></Entity></Entities>'
        '<Limits SoftLimit="100" HardLimit="100"/>'
        '</MaltegoTransformRequestMessage></MaltegoMessage>'
    )
    req = MaltegoMsg(xml)
    resp = MaltegoTransform()

    ProfileToIP.create_entities(req, resp)

    assert len(resp.entities) == 0
    assert len(resp.UIMessages) == 1
    assert "No user profile specified" in str(resp.UIMessages[0])


def test_profile_to_ip_mock_execution(monkeypatch):
    import transforms.ProfileToIP as p2ip
    from transforms.ProfileToIP import ProfileToIP, Candidate

    fake_cand = Candidate(address="93.184.216.34", port=54321, protocol="udp", kind="srflx")
    def _mock_run(coro):
        coro.close()
        return [fake_cand]
    monkeypatch.setattr(p2ip, "run_telegram", _mock_run)

    xml = (
        '<MaltegoMessage><MaltegoTransformRequestMessage><Entities><Entity Type="interlinked.telegram.UserProfile">'
        '<Value>testuser</Value><Weight>100</Weight><AdditionalFields>'
        '<Field Name="properties.username">testuser</Field>'
        '</AdditionalFields></Entity></Entities>'
        '<Limits SoftLimit="100" HardLimit="100"/>'
        '</MaltegoTransformRequestMessage></MaltegoMessage>'
    )
    req = MaltegoMsg(xml)
    resp = MaltegoTransform()

    ProfileToIP.create_entities(req, resp)

    assert len(resp.entities) == 1
    entity = resp.entities[0]
    assert entity.entityType == "maltego.IPv4Address"
    assert entity.value == "93.184.216.34"
    props = {field[0]: field[3] for field in entity.additionalFields}
    assert props["ipv4-address"] == "93.184.216.34"
    assert props["properties.port"] == "54321"
    assert props["properties.protocol"] == "UDP"
    assert props["properties.type"] == "srflx"

