"""
Tests for ChannelToBotReferrals transform using synthetic mock data.
"""

from unittest.mock import MagicMock
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.enums import MessageEntityType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, MessageEntity

from transforms.ChannelToBotReferrals import (
    ChannelToBotReferrals,
    ReferralLinkItem,
    extract_referrals_from_message,
    extract_text_slice,
    parse_bot_referral,
)


def test_extract_text_slice():
    # Simple ASCII
    text = "Hello click here now"
    assert extract_text_slice(text, 6, 10) == "click here"

    # With Telegram emoji (UTF-16 surrogate pairs)
    # In UTF-16: '🚀' takes 2 code units, ' ' takes 1 unit
    emoji_text = "🚀 Launch the bot"
    # Offset 3 (2 for emoji + 1 for space), length 14 ("Launch the bot")
    assert extract_text_slice(emoji_text, 3, 14) == "Launch the bot"

    # Edge cases
    assert extract_text_slice("", 0, 5) is None
    assert extract_text_slice(None, 0, 5) is None
    assert extract_text_slice("test", -1, 2) is None
    assert extract_text_slice("test", 0, 0) is None


def test_parse_bot_referral_standard():
    url = "https://t.me/example_bot?start=invite_12345678"
    match = parse_bot_referral(url)
    assert match is not None
    assert match.url == "https://t.me/example_bot?start=invite_12345678"
    assert match.bot_username == "example_bot"
    assert match.referral_param == "start"
    assert match.referral_code == "invite_12345678"


def test_parse_bot_referral_variations():
    # Telegram.me domain
    match1 = parse_bot_referral("https://telegram.me/alpha_bot?start=ref123")
    assert match1 is not None
    assert match1.bot_username == "alpha_bot"
    assert match1.referral_code == "ref123"

    # Schemeless t.me
    match2 = parse_bot_referral("t.me/beta_bot?start=pay_456")
    assert match2 is not None
    assert match2.bot_username == "beta_bot"
    assert match2.referral_code == "pay_456"

    # tg:// protocol
    match3 = parse_bot_referral("tg://resolve?domain=example_bot&start=invite_12345678")
    assert match3 is not None
    assert match3.bot_username == "example_bot"
    assert match3.url == "https://t.me/example_bot?start=invite_12345678"
    assert match3.referral_code == "invite_12345678"

    # Mini App startapp parameter
    match4 = parse_bot_referral("https://t.me/delta_bot/app?startapp=user_999")
    assert match4 is not None
    assert match4.bot_username == "delta_bot"
    assert match4.referral_param == "startapp"
    assert match4.referral_code == "user_999"
    assert match4.url == "https://t.me/delta_bot/app?startapp=user_999"

    # Trailing punctuation in text
    match5 = parse_bot_referral("https://t.me/example_bot?start=invite_12345678.")
    assert match5 is not None
    assert match5.referral_code == "invite_12345678"

    # Multiple query params
    match6 = parse_bot_referral("https://t.me/example_bot?utm_source=tg&start=invite_12345678")
    assert match6 is not None
    assert match6.referral_code == "invite_12345678"


def test_parse_bot_referral_negatives():
    # Regular channel link
    assert parse_bot_referral("https://t.me/sample_channel") is None

    # Channel post
    assert parse_bot_referral("https://t.me/sample_channel/123") is None

    # Bot link without referral code
    assert parse_bot_referral("https://t.me/example_bot") is None

    # Empty start param
    assert parse_bot_referral("https://t.me/example_bot?start=") is None

    # Private chat invite
    assert parse_bot_referral("https://t.me/+AbCdEfGhIj") is None

    # Reserved telegram paths
    assert parse_bot_referral("https://t.me/joinchat/AbCdEfGhIj?start=123") is None
    assert parse_bot_referral("https://t.me/s/sample_channel?start=123") is None

    # Non-telegram URL
    assert parse_bot_referral("https://example.com/bot?start=invite_123") is None


def test_extract_referrals_from_message():
    # Create mock message with inline button, text link entity, and plain text
    msg = MagicMock(spec=Message)
    msg.id = 42
    raw_text = "Check out our test bot: https://t.me/example_bot?start=invite_12345678! Also click the link: Referral bot"
    msg.text = raw_text
    msg.caption = None
    msg.forward_from_chat = None
    msg.forward_from = None
    msg.web_page = None

    # Inline button
    btn = MagicMock(spec=InlineKeyboardButton)
    btn.text = "Launch bot"
    btn.url = "https://t.me/example_bot?start=invite_12345678"
    btn.web_app = None

    markup = MagicMock(spec=InlineKeyboardMarkup)
    markup.inline_keyboard = [[btn]]
    msg.reply_markup = markup

    # Text link entity pointing to anchor "Referral bot"
    anchor = "Referral bot"
    offset = raw_text.index(anchor)
    entity = MagicMock(spec=MessageEntity)
    entity.type = MessageEntityType.TEXT_LINK
    entity.url = "https://t.me/gamma_bot?start=ref_888"
    entity.offset = offset
    entity.length = len(anchor)
    msg.entities = [entity]
    msg.caption_entities = None

    extracted = extract_referrals_from_message(msg, "sample_channel")

    # Should find 2 unique referral links (button + text link, deduplicated with plain text)
    assert len(extracted) == 2
    urls = [item.match.url for item in extracted]
    assert "https://t.me/example_bot?start=invite_12345678" in urls
    assert "https://t.me/gamma_bot?start=ref_888" in urls

    # Check button context for example_bot
    example_item = [item for item in extracted if item.match.bot_username == "example_bot"][0]
    assert example_item.button_text == "Launch bot"

    # Check hyperlink text for gamma_bot
    gamma_item = [item for item in extracted if item.match.bot_username == "gamma_bot"][0]
    assert gamma_item.link_text == "Referral bot"


def test_channel_to_bot_referrals_transform(monkeypatch):
    import transforms.ChannelToBotReferrals as c2b

    fake_item = ReferralLinkItem(
        url="https://t.me/example_bot?start=invite_12345678",
        bot_username="example_bot",
        referral_param="start",
        referral_code="invite_12345678",
        first_post_id=10,
        last_post_id=25,
        mention_count=2,
        post_urls=["https://t.me/sample_channel/10", "https://t.me/sample_channel/25"],
        button_texts=["Launch bot"],
        link_texts=["Click here"],
        is_forwarded=False,
    )

    def _mock_run(coro):
        coro.close()
        return [fake_item]

    monkeypatch.setattr(c2b, "run_telegram", _mock_run)

    xml = (
        '<MaltegoMessage><MaltegoTransformRequestMessage><Entities><Entity Type="interlinked.telegram.Channel">'
        '<Value>sample_channel</Value><Weight>100</Weight><AdditionalFields>'
        '<Field Name="properties.channel">sample_channel</Field>'
        '</AdditionalFields></Entity></Entities>'
        '<Limits SoftLimit="100" HardLimit="100"/>'
        '</MaltegoTransformRequestMessage></MaltegoMessage>'
    )
    req = MaltegoMsg(xml)
    resp = MaltegoTransform()

    ChannelToBotReferrals.create_entities(req, resp)

    assert len(resp.entities) == 1
    entity = resp.entities[0]
    assert entity.entityType == "maltego.URL"
    assert entity.value == "https://t.me/example_bot?start=invite_12345678"

    props = {field[0]: field[3] for field in entity.additionalFields}
    assert props["url"] == "https://t.me/example_bot?start=invite_12345678"
    assert props["properties.bot"] == "@example_bot"
    assert props["properties.code"] == "invite_12345678"
    assert props["properties.param"] == "start"
    assert props["properties.mentions"] == "2"
    assert props["properties.post_url"] == "https://t.me/sample_channel/10"
    assert props["properties.button_text"] == "Launch bot"
    assert props["properties.link_text"] == "Click here"


def test_channel_to_bot_referrals_missing_channel():
    xml = (
        '<MaltegoMessage><MaltegoTransformRequestMessage><Entities><Entity Type="interlinked.telegram.Channel">'
        '<Value></Value><Weight>100</Weight></Entity></Entities>'
        '<Limits SoftLimit="100" HardLimit="100"/>'
        '</MaltegoTransformRequestMessage></MaltegoMessage>'
    )
    req = MaltegoMsg(xml)
    resp = MaltegoTransform()

    ChannelToBotReferrals.create_entities(req, resp)

    assert len(resp.entities) == 0
    assert len(resp.UIMessages) == 1
    assert "No channel specified" in str(resp.UIMessages[0])
