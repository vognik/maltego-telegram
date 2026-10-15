"""
Tests for BotReferralToProfile transform using synthetic mock data.
"""

from unittest.mock import MagicMock
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.types import User

from transforms.BotReferralToProfile import (
    BotReferralToProfile,
    extract_profile_id_from_referral,
)


def test_extract_profile_id_from_referral_various_formats():
    # Common invite_ prefix
    assert (
        extract_profile_id_from_referral("https://t.me/example_bot?start=invite_12345678")
        == 12345678
    )

    # Pure numeric start parameter
    assert (
        extract_profile_id_from_referral("https://t.me/example_bot?start=12345678")
        == 12345678
    )

    # Other common prefixes: ref_, user_, id, u, r, c
    assert (
        extract_profile_id_from_referral("https://t.me/example_bot?start=ref_987654321")
        == 987654321
    )
    assert (
        extract_profile_id_from_referral("https://t.me/example_bot?start=user_555666777")
        == 555666777
    )
    assert (
        extract_profile_id_from_referral("https://t.me/example_bot?start=id888999000")
        == 888999000
    )
    assert (
        extract_profile_id_from_referral("https://t.me/example_bot?start=c_111222333")
        == 111222333
    )

    # Mini App startapp parameter
    assert (
        extract_profile_id_from_referral("https://t.me/example_bot/app?startapp=invite_12345678")
        == 12345678
    )

    # Telegram protocol deep link
    assert (
        extract_profile_id_from_referral("tg://resolve?domain=example_bot&start=invite_12345678")
        == 12345678
    )

    # Raw referral code without URL
    assert extract_profile_id_from_referral("invite_12345678") == 12345678
    assert extract_profile_id_from_referral("12345678") == 12345678


def test_extract_profile_id_negatives():
    # Non-numeric referral codes
    assert extract_profile_id_from_referral("https://t.me/example_bot?start=welcome") is None
    assert extract_profile_id_from_referral("https://t.me/example_bot?start=promo_code") is None

    # Too short to be a Telegram profile ID
    assert extract_profile_id_from_referral("https://t.me/example_bot?start=123") is None

    # Empty inputs
    assert extract_profile_id_from_referral("") is None
    assert extract_profile_id_from_referral(None) is None


def test_bot_referral_to_profile_transform(monkeypatch):
    import transforms.BotReferralToProfile as b2p

    mock_user = User(
        id=12345678,
        username="sample_owner",
        first_name="Sample",
        last_name="Owner",
    )

    def _mock_run(coro):
        coro.close()
        return mock_user, None, 12345678

    monkeypatch.setattr(b2p, "run_telegram", _mock_run)

    xml = (
        '<MaltegoMessage><MaltegoTransformRequestMessage><Entities><Entity Type="maltego.URL">'
        '<Value>https://t.me/example_bot?start=invite_12345678</Value><Weight>100</Weight><AdditionalFields>'
        '<Field Name="url">https://t.me/example_bot?start=invite_12345678</Field>'
        '<Field Name="properties.code">invite_12345678</Field>'
        '</AdditionalFields></Entity></Entities>'
        '<Limits SoftLimit="100" HardLimit="100"/>'
        '</MaltegoTransformRequestMessage></MaltegoMessage>'
    )
    req = MaltegoMsg(xml)
    resp = MaltegoTransform()

    BotReferralToProfile.create_entities(req, resp)

    assert len(resp.entities) == 1
    entity = resp.entities[0]
    assert entity.entityType == "interlinked.telegram.UserProfile"
    assert entity.value == "sample_owner"

    props = {field[0]: field[3] for field in entity.additionalFields}
    assert props["properties.id"] == "12345678"
    assert props["properties.username"] == "sample_owner"
    assert props["properties.extracted_id"] == "12345678"


def test_bot_referral_to_profile_no_id_found():
    xml = (
        '<MaltegoMessage><MaltegoTransformRequestMessage><Entities><Entity Type="maltego.URL">'
        '<Value>https://t.me/example_bot?start=non_numeric_promo</Value><Weight>100</Weight>'
        '</Entity></Entities>'
        '<Limits SoftLimit="100" HardLimit="100"/>'
        '</MaltegoTransformRequestMessage></MaltegoMessage>'
    )
    req = MaltegoMsg(xml)
    resp = MaltegoTransform()

    BotReferralToProfile.create_entities(req, resp)

    assert len(resp.entities) == 0
    assert len(resp.UIMessages) == 1
    assert "No profile ID could be extracted" in str(resp.UIMessages[0])


def test_bot_referral_to_profile_empty_request():
    xml = (
        '<MaltegoMessage><MaltegoTransformRequestMessage><Entities><Entity Type="maltego.URL">'
        '<Value></Value><Weight>100</Weight>'
        '</Entity></Entities>'
        '<Limits SoftLimit="100" HardLimit="100"/>'
        '</MaltegoTransformRequestMessage></MaltegoMessage>'
    )
    req = MaltegoMsg(xml)
    resp = MaltegoTransform()

    BotReferralToProfile.create_entities(req, resp)

    assert len(resp.entities) == 0
    assert len(resp.UIMessages) == 1
    assert "No URL or referral code specified" in str(resp.UIMessages[0])
