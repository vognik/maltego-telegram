"""
Unit tests for TgScan API adapter and configuration.
Verifies production and test key handling, URL routing, and response parsing.
"""

import json
from unittest.mock import patch, MagicMock
import settings

from adapters.tgscan import (
    query_tgscan,
    TGSCAN_PROD_URL,
    TGSCAN_TEST_URL,
)
from settings import get_tgscan_credentials


def test_tgscan_credentials_resolution():
    """Verify production vs test URL and key resolution."""
    # Test mode True -> test endpoint
    url, key = get_tgscan_credentials(test_mode=True)
    assert url == settings.TGSCAN_URL_TEST

    # Test mode False -> prod endpoint
    url, key = get_tgscan_credentials(test_mode=False)
    assert url == settings.TGSCAN_URL_PROD


def test_tgscan_custom_urls_from_config():
    """Verify that custom URLs in config.ini are respected."""
    with patch.object(settings.config, "get", side_effect=lambda sec, key, fallback="": {
        ("tgscan", "url_prod"): "https://custom.tgscan.io/prod",
        ("tgscan", "url_test"): "https://custom.tgscan.io/test",
        ("tgscan", "api_key_prod"): "prod_key_123",
        ("tgscan", "api_key_test"): "test_key_456",
    }.get((sec, key), fallback)):
        with patch.object(settings, "TGSCAN_URL_PROD", "https://custom.tgscan.io/prod"), \
             patch.object(settings, "TGSCAN_URL_TEST", "https://custom.tgscan.io/test"), \
             patch.object(settings, "TGSCAN_API_KEY_PROD", "prod_key_123"), \
             patch.object(settings, "TGSCAN_API_KEY_TEST", "test_key_456"):
            
            prod_url, prod_key = get_tgscan_credentials(test_mode=False)
            assert prod_url == "https://custom.tgscan.io/prod"
            assert prod_key == "prod_key_123"

            test_url, test_key = get_tgscan_credentials(test_mode=True)
            assert test_url == "https://custom.tgscan.io/test"
            assert test_key == "test_key_456"


def test_tgscan_prod_key_routing():
    """Verify that prod key queries production URL."""
    fake_response = {
        "status": "ok",
        "result": {
            "user": {"id": 12345, "username": "testuser", "first_name": "Test"},
            "meta": {"known_num_groups": 2, "num_groups": 2, "op_cost": 1},
            "groups": [
                {"id": -1001111111111, "title": "Prod Group 1", "username": "prod_group1", "date_updated": "2024-01-01"},
                {"id": -1002222222222, "title": "Prod Group 2", "username": None, "date_updated": "2024-01-02"},
            ],
        },
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fake_response).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        res = query_tgscan("testuser", api_key="my_prod_key", test_mode=False)
        assert res is not None
        assert res.is_test is False
        assert len(res.groups) == 2
        assert res.groups[0].identifier == "prod_group1"
        assert res.groups[1].identifier == "-1002222222222"
        assert res.groups[0].title == "Prod Group 1"

        # Check request sent to urlopen
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == TGSCAN_PROD_URL
        assert req.headers["Api-key"] == "my_prod_key"
        assert b"query=testuser" in req.data


def test_tgscan_test_key_routing():
    """Verify that test key queries test URL."""
    fake_response = {
        "status": "ok",
        "result": {
            "user": {"id": 99999, "username": "random_mock", "first_name": "Mock"},
            "meta": {"known_num_groups": 1, "num_groups": 1, "op_cost": 0},
            "groups": [
                {"id": -1009999999999, "title": "Test Random Group", "username": "test_grp", "date_updated": "2024-02-01"}
            ],
        },
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fake_response).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        res = query_tgscan("sample_target", api_key="my_test_key", test_mode=True)
        assert res is not None
        assert res.is_test is True
        assert len(res.groups) == 1
        assert res.groups[0].title == "Test Random Group"
        assert res.groups[0].identifier == "test_grp"

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == TGSCAN_TEST_URL
        assert req.headers["Api-key"] == "my_test_key"


def test_tgscan_error_handling():
    """Verify graceful handling when TgScan returns an error status."""
    fake_error = {
        "status": "error",
        "result": {"message": "Invalid API key"},
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fake_error).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = query_tgscan("testuser", api_key="bad_key")
        assert res is None


def test_tgscan_empty_key():
    """Verify that query_tgscan returns None when no key is available."""
    with patch("adapters.tgscan.get_tgscan_credentials", return_value=(TGSCAN_PROD_URL, "")):
        res = query_tgscan("testuser", api_key="")
        assert res is None
