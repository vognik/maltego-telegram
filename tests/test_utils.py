"""
Unit tests for utils.py helpers and regex parsing.
"""

from utils import (
    normalize_identifier,
    normalize_phone,
    extract_username_from_text,
    extract_group_links_from_text,
    get_color,
    get_default_photo_b64,
)


def test_normalize_identifier():
    assert normalize_identifier("@sample_target") == "sample_target"
    assert normalize_identifier("https://t.me/sample_target") == "sample_target"
    assert normalize_identifier("http://t.me/sample_target/") == "sample_target"
    assert normalize_identifier("t.me/sample_channel") == "sample_channel"
    assert normalize_identifier("  @test_channel  ") == "test_channel"
    assert normalize_identifier("already_clean") == "already_clean"
    assert normalize_identifier("") == ""
    assert normalize_identifier(None) == ""


def test_normalize_phone():
    assert normalize_phone("+1 (234) 567-8900") == "+12345678900"
    assert normalize_phone("8 800 555 35 35") == "88005553535"
    assert normalize_phone("+7-999-123-45-67") == "+79991234567"
    assert normalize_phone("") == ""


def test_extract_username_from_bot_response():
    # Example format received from bot dialog (synthetic test data)
    bot_response_text = (
        "👤 \u20631234567890\n"
        "\u2063👦🏻 Test User\n"
        "\u2063🌐 @test_sample_user\n"
        "🕑 Updated at 11/10/2026"
    )
    extracted = extract_username_from_text(bot_response_text)
    assert extracted == "test_sample_user"


def test_extract_username_various_formats():
    # Plain @mention
    assert extract_username_from_text("Owner of pack: @sample_user1") == "sample_user1"

    # t.me link
    assert extract_username_from_text("Check profile at https://t.me/sample_user2") == "sample_user2"

    # Labeled
    assert extract_username_from_text("Username: sample_user3\nID: 123") == "sample_user3"
    assert extract_username_from_text("Login: @sample_user4") == "sample_user4"

    # Standalone line
    assert extract_username_from_text("sample_user5") == "sample_user5"

    # Negative / None cases
    assert extract_username_from_text("") is None
    assert extract_username_from_text("No user found for this ID") is None
    assert extract_username_from_text("123456789") is None


def test_extract_group_links():
    text = (
        "Found groups:\n"
        "1. @sample_group_one\n"
        "2. https://t.me/sample_group_two\n"
        "3. t.me/sample_group_three\n"
    )
    groups = extract_group_links_from_text(text)
    assert "sample_group_one" in groups
    assert "sample_group_two" in groups
    assert "sample_group_three" in groups


def test_default_photo_and_color():
    color1 = get_color(123456)
    color2 = get_color(654321)
    assert color1.startswith("#")
    assert color2.startswith("#")

    b64 = get_default_photo_b64(123456)
    assert isinstance(b64, str)
    assert len(b64) > 50
