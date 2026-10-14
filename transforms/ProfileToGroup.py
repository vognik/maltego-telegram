"""
Transform: Profile to Groups
Finds public Telegram groups associated with a user profile using:
1. TgScan API (tgdev.io) with support for Production and Test API keys.
2. Fallback to MTProto bot (config.ini [bots] group_search_bot).
"""

import asyncio
from dataclasses import dataclass
from typing import List, Optional, Tuple
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.types import Chat

from extensions import registry
from client import run_telegram, get_client
from settings import GROUP_SEARCH_BOT, CONCURRENCY, TIMEOUT
from adapters.tgscan import async_query_tgscan
from utils import (
    safe_get_identifier,
    normalize_identifier,
    download_avatar_b64,
    query_inline_bot,
    query_bot_dialog,
    extract_group_links_from_text,
)


@dataclass
class ResolvedGroup:
    chat: Optional[Chat]
    identifier: str
    title: str
    avatar_b64: Optional[str] = None
    group_id: Optional[int] = None
    source: str = "mtproto"
    date_updated: Optional[str] = None


async def search_user_groups(
    query: str,
    api_key: Optional[str] = None,
    test_mode: Optional[bool] = None,
) -> List[ResolvedGroup]:
    """
    Search for groups associated with a Telegram user profile.
    Supports TgScan API (both Production and Test keys) with automatic
    fallback to MTProto bot dialog.
    """
    client = get_client()
    clean_query = normalize_identifier(query)
    if not clean_query:
        return []

    discovered_groups: List[Tuple[str, str, Optional[int], Optional[str], str]] = []
    # (identifier, title, group_id, date_updated, source)

    # 1. Try TgScan API if configured (prod or test key)
    try:
        tgscan_res = await async_query_tgscan(clean_query, api_key=api_key, test_mode=test_mode)
        if tgscan_res and tgscan_res.groups:
            source_label = "tgscan_test" if tgscan_res.is_test else "tgscan_prod"
            for g in tgscan_res.groups:
                discovered_groups.append(
                    (g.identifier, g.title, g.id, g.date_updated, source_label)
                )
    except Exception:
        pass

    # 2. Fall back to MTProto bot if no TgScan results
    if not discovered_groups and GROUP_SEARCH_BOT:
        mtproto_groups: List[str] = []
        try:
            inline_results = await query_inline_bot(client, GROUP_SEARCH_BOT, clean_query)
            if inline_results:
                for res in inline_results:
                    msg_text = getattr(res.send_message, "message", "") or getattr(res, "description", "")
                    groups = extract_group_links_from_text(msg_text)
                    mtproto_groups.extend(groups)
        except Exception:
            pass

        if not mtproto_groups:
            reply_message = await query_bot_dialog(
                client,
                bot_username=GROUP_SEARCH_BOT,
                query_text=f"@{clean_query}",
                timeout=float(TIMEOUT),
            )
            if reply_message and reply_message.text:
                mtproto_groups = extract_group_links_from_text(
                    reply_message.text, reply_message.entities
                )

        for g in mtproto_groups:
            cleaned = normalize_identifier(g)
            if cleaned:
                discovered_groups.append((cleaned, cleaned, None, None, "mtproto_bot"))

    # Deduplicate group identifiers
    seen = set()
    unique_groups = []
    for ident, title, gid, date_upd, src in discovered_groups:
        ident_lower = ident.lower()
        if ident_lower not in seen:
            seen.add(ident_lower)
            unique_groups.append((ident, title, gid, date_upd, src))

    if not unique_groups:
        return []

    # Limit to top 15 groups for Maltego graph clarity
    unique_groups = unique_groups[:15]

    # 3. Resolve groups and download avatars via MTProto concurrently
    sem = asyncio.Semaphore(CONCURRENCY)

    async def _resolve_group(
        ident: str, default_title: str, gid: Optional[int], date_upd: Optional[str], src: str
    ) -> ResolvedGroup:
        async with sem:
            try:
                chat = await client.get_chat(ident)
                avatar_b64 = await download_avatar_b64(client, chat)
                return ResolvedGroup(
                    chat=chat,
                    identifier=chat.username or str(chat.id),
                    title=chat.title or default_title,
                    avatar_b64=avatar_b64,
                    group_id=chat.id if chat else gid,
                    source=src,
                    date_updated=date_upd,
                )
            except Exception:
                return ResolvedGroup(
                    chat=None,
                    identifier=ident,
                    title=default_title,
                    avatar_b64=None,
                    group_id=gid,
                    source=src,
                    date_updated=date_upd,
                )

    results = await asyncio.gather(
        *(_resolve_group(i, t, gid, d, s) for i, t, gid, d, s in unique_groups)
    )
    return results


# Backwards compatibility alias
search_user_groups_mtproto = search_user_groups


@registry.register_transform(
    display_name="To Groups",
    input_entity="interlinked.telegram.UserProfile",
    description="Finds public Telegram groups associated with a user profile via TgScan API or MTProto bot",
    output_entities=["interlinked.telegram.Group"],
)
class ProfileToGroup(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = (
            safe_get_identifier(request, "properties.username")
            or safe_get_identifier(request, "properties.channel")
            or safe_get_identifier(request, "properties.id")
            or getattr(request, "Value", None)
        )
        if not username:
            response.addUIMessage("No username or ID specified", messageType="PartialError")
            return

        # Check transform settings for TgScan overrides
        setting_api_key = request.getTransformSetting("tgscan_api_key") or None
        setting_test_mode = None
        test_mode_str = request.getTransformSetting("tgscan_test_mode")
        if test_mode_str:
            setting_test_mode = test_mode_str.lower() in ("true", "1", "yes", "test")

        try:
            groups = run_telegram(
                search_user_groups(
                    username,
                    api_key=setting_api_key,
                    test_mode=setting_test_mode,
                )
            )
            if not groups:
                response.addUIMessage("No associated groups found", messageType="Inform")
                return

            for group in groups:
                entity = response.addEntity("interlinked.telegram.Group", value=group.identifier)
                entity.addProperty("properties.title", value=group.title)
                if group.avatar_b64:
                    entity.addProperty("base64", value=group.avatar_b64)

                if group.group_id:
                    entity.addProperty("properties.id", value=str(group.group_id))

                if group.date_updated:
                    entity.addProperty("properties.date_updated", value=str(group.date_updated))

                if group.source:
                    entity.addProperty("properties.source", value=str(group.source))

                if group.chat:
                    chat = group.chat
                    entity.addProperty("properties.id", value=str(chat.id))
                    if chat.username:
                        entity.addProperty("properties.username", value=chat.username)
                    if getattr(chat, "members_count", None):
                        entity.addProperty("properties.members_count", value=str(chat.members_count))
                    if getattr(chat, "description", None):
                        entity.addProperty("properties.description", value=chat.description[:200])

                entity.setLinkThickness(2)

        except Exception as e:
            response.addUIMessage(f"Error querying groups: {e}", messageType="PartialError")