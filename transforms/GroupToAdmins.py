"""
Transform: Group to Admins
Finds all administrators of a Telegram group or supergroup via MTProto.
"""

import asyncio
from typing import List, Tuple
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram import enums
from pyrogram.types import User

from extensions import registry
from client import run_telegram, get_client
from settings import CONCURRENCY
from utils import safe_get_identifier, normalize_identifier, download_avatar_b64, process_profile_entity


async def fetch_group_admins(identifier: str) -> List[Tuple[User, str]]:
    client = get_client()
    clean_id = normalize_identifier(identifier)
    admins: List[User] = []

    async for member in client.get_chat_members(clean_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
        if member.user:
            admins.append(member.user)

    sem = asyncio.Semaphore(CONCURRENCY)

    async def _fetch_avatar(u: User):
        async with sem:
            b64 = await download_avatar_b64(client, u)
            return u, b64

    results = []
    if admins:
        results = await asyncio.gather(*(_fetch_avatar(u) for u in admins))

    return results


@registry.register_transform(
    display_name="To Group Admins",
    input_entity="interlinked.telegram.Group",
    description="Finds administrators of a Telegram group with profile metadata and avatars",
    output_entities=["interlinked.telegram.UserProfile"],
)
class GroupToAdmins(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = safe_get_identifier(request, "properties.username")
        if not identifier:
            response.addUIMessage("No group specified", messageType="PartialError")
            return

        try:
            admins_with_avatars = run_telegram(fetch_group_admins(identifier))
            for admin_user, avatar_b64 in admins_with_avatars:
                entity = process_profile_entity(admin_user, avatar_b64=avatar_b64)
                entity.setLinkThickness(2)
                response.entities.append(entity)
        except Exception as e:
            response.addUIMessage(f"Error fetching group administrators: {e}", messageType="PartialError")
