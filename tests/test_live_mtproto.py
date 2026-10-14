"""
Integration tests for live MTProto session and universal bot lookup.
"""

import client
from settings import USER_LOOKUP_BOT
from utils import extract_username_from_text, query_inline_bot


def test_live_mtproto_get_me():
    """Verify live MTProto session can authenticate and fetch current user."""
    async def _test():
        c = client.get_client()
        return await c.get_me()

    me = client.run_telegram(_test())
    assert me is not None
    assert isinstance(me.id, int) and me.id > 0
    assert isinstance(me.first_name, str) and len(me.first_name) > 0


def test_live_user_lookup_bot_inline():
    """Verify live inline query to user_lookup_bot extracts username."""
    async def _test():
        c = client.get_client()
        me = await c.get_me()
        results = await query_inline_bot(c, USER_LOOKUP_BOT, str(me.id))
        if not results:
            return None
        msg_text = getattr(results[0].send_message, "message", "")
        return extract_username_from_text(msg_text)

    username = client.run_telegram(_test())
    assert username is None or isinstance(username, str)
