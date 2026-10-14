"""
Unit tests for configuration loading and universal bot naming.
"""

from settings import Config, USER_LOOKUP_BOT, GROUP_SEARCH_BOT


def test_config_loader(tmp_path):
    mock_ini = tmp_path / "mock_config.ini"
    mock_ini.write_text("[telegram]\napi_id = 12345678\napi_hash = 0123456789abcdef0123456789abcdef\n", encoding="utf-8")
    cfg = Config(filename=str(mock_ini))
    assert cfg.get_int("telegram", "api_id") == 12345678
    assert cfg.get("telegram", "api_hash") == "0123456789abcdef0123456789abcdef"

    default_cfg = Config()
    assert isinstance(default_cfg.get_int("telegram", "api_id"), int)
    assert isinstance(default_cfg.get("telegram", "api_hash"), str)


def test_universal_bot_naming():
    cfg = Config()
    # Check that universal keys are read from config.ini
    user_bot = cfg.get_bot("user_lookup_bot")
    assert isinstance(user_bot, str) and len(user_bot) > 0

    group_bot = cfg.get_bot("group_search_bot")
    assert isinstance(group_bot, str) and len(group_bot) > 0

    # Check imported settings match configured bots
    assert USER_LOOKUP_BOT == user_bot
    assert GROUP_SEARCH_BOT == group_bot


def test_bot_name_stripping_at_sign():
    cfg = Config()
    assert cfg.get_bot("nonexistent", fallback="@mybot") == "mybot"
    assert cfg.get_bot("nonexistent", fallback="mybot") == "mybot"


def test_config_fallbacks():
    cfg = Config()
    assert cfg.get("misc", "nonexistent", fallback="default_val") == "default_val"
    assert cfg.get_int("misc", "nonexistent", fallback=42) == 42
    assert cfg.get_bool("misc", "nonexistent", fallback=True) is True


def test_tgscan_config_section():
    cfg = Config()
    assert cfg.get_bool("tgscan", "test_mode", fallback=False) is False
    assert cfg.get("tgscan", "url_prod", fallback="https://api.tgdev.io/tgscan/v1/search") == "https://api.tgdev.io/tgscan/v1/search"
    assert cfg.get("tgscan", "url_test", fallback="https://api.tgdev.io/tgscan/v1/test/search") == "https://api.tgdev.io/tgscan/v1/test/search"
