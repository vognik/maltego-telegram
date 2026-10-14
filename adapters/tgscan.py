"""
TgScan (tgdev.io) API Adapter.
Provides search for Telegram user groups with support for both Production and Test API keys.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.parse
import urllib.error

from settings import (
    TGSCAN_URL_PROD,
    TGSCAN_URL_TEST,
    TIMEOUT,
    get_tgscan_credentials,
)

logger = logging.getLogger("maltego_telegram.tgscan")

TGSCAN_PROD_URL = TGSCAN_URL_PROD
TGSCAN_TEST_URL = TGSCAN_URL_TEST


@dataclass
class TgScanGroup:
    id: int
    title: str
    username: Optional[str] = None
    date_updated: Optional[str] = None

    @property
    def identifier(self) -> str:
        """Returns the best identifier for Maltego (username without @, or numeric ID)."""
        if self.username:
            return self.username.lstrip("@")
        return str(self.id)


@dataclass
class TgScanResult:
    user: Optional[Dict[str, Any]]
    groups: List[TgScanGroup]
    meta: Dict[str, Any]
    is_test: bool = False
    raw: Optional[Dict[str, Any]] = None


def query_tgscan(
    query: str,
    api_key: Optional[str] = None,
    test_mode: Optional[bool] = None,
    timeout: Optional[float] = None,
) -> Optional[TgScanResult]:
    """
    Query the TgScan API for a user's associated groups.
    Supports both production and test API endpoints/keys.

    :param query: Username (without @) or Telegram numeric user ID.
    :param api_key: Explicit API key to override configured keys.
    :param test_mode: Explicit flag to force test or production endpoint.
    :param timeout: Request timeout in seconds.
    :return: TgScanResult if successful, None otherwise.
    """
    clean_query = str(query).strip().lstrip("@")
    if not clean_query:
        return None

    # Resolve URL and API key
    if test_mode is not None:
        url, resolved_key = get_tgscan_credentials(test_mode=test_mode)
    else:
        url, resolved_key = get_tgscan_credentials()

    final_key = api_key or resolved_key
    if not final_key:
        logger.debug("No TgScan API key configured.")
        return None

    is_test_call = (url == TGSCAN_TEST_URL) or (test_mode is True)
    req_timeout = timeout or float(TIMEOUT) or 15.0

    headers = {
        "Api-Key": final_key,
        "User-Agent": "Maltego-Telegram-TgScan/1.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    encoded_data = urllib.parse.urlencode({"query": clean_query}).encode("utf-8")
    req = urllib.request.Request(url, data=encoded_data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=req_timeout) as resp:
            content = resp.read().decode("utf-8")
            data = json.loads(content)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        logger.warning(f"TgScan HTTP {e.code} error: {err_body}")
        return None
    except Exception as e:
        logger.warning(f"TgScan connection error ({url}): {e}")
        return None

    if data.get("status") != "ok":
        err_msg = data.get("result", {}).get("message", "Unknown error")
        logger.warning(f"TgScan API error response: {err_msg}")
        return None

    result = data.get("result", {})
    raw_groups = result.get("groups", [])
    parsed_groups: List[TgScanGroup] = []

    for g in raw_groups:
        try:
            gid = int(g.get("id"))
            title = g.get("title") or str(gid)
            username = g.get("username")
            if username:
                username = username.lstrip("@")
            date_upd = g.get("date_updated")
            parsed_groups.append(
                TgScanGroup(
                    id=gid,
                    title=title,
                    username=username,
                    date_updated=date_upd,
                )
            )
        except (ValueError, TypeError):
            continue

    return TgScanResult(
        user=result.get("user"),
        groups=parsed_groups,
        meta=result.get("meta", {}),
        is_test=is_test_call,
        raw=data,
    )


async def async_query_tgscan(
    query: str,
    api_key: Optional[str] = None,
    test_mode: Optional[bool] = None,
    timeout: Optional[float] = None,
) -> Optional[TgScanResult]:
    """Asynchronous wrapper for query_tgscan executing in a worker thread."""
    return await asyncio.to_thread(query_tgscan, query, api_key, test_mode, timeout)
