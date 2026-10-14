"""
Transform: Channel to Forwarded Users
Identifies real user profiles and sender names forwarded into this channel.
"""

import asyncio
from typing import Dict, List, Set, Tuple
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.types import User

from extensions import registry
from client import run_telegram, get_client
from settings import LIMIT, CONCURRENCY
from utils import safe_get_identifier, normalize_identifier, download_avatar_b64, process_profile_entity


async def fetch_forwarded_users_and_authors(
    identifier: str,
) -> Tuple[List[Tuple[User, str]], List[str]]:
    client = get_client()
    clean_id = normalize_identifier(identifier)

    unique_users: Dict[int, User] = {}
    unique_authors: Set[str] = set()

    async for message in client.get_chat_history(clean_id, limit=LIMIT):
        if message.forward_from and isinstance(message.forward_from, User):
            if message.forward_from.id not in unique_users:
                unique_users[message.forward_from.id] = message.forward_from
        elif message.forward_sender_name:
            name = message.forward_sender_name.strip()
            if name:
                unique_authors.add(name)

    # Concurrently fetch user avatars via MTProto
    users = list(unique_users.values())
    sem = asyncio.Semaphore(CONCURRENCY)

    async def _fetch_avatar(u: User):
        async with sem:
            b64 = await download_avatar_b64(client, u)
            return u, b64

    users_with_avatars = []
    if users:
        users_with_avatars = await asyncio.gather(*(_fetch_avatar(u) for u in users))

    return users_with_avatars, sorted(unique_authors)


@registry.register_transform(
    display_name="To Forwarded Users",
    input_entity="interlinked.telegram.Channel",
    description="Receives all user profiles and sender names whose messages were forwarded into this channel",
    output_entities=["interlinked.telegram.UserProfile", "interlinked.telegram.Author"],
)
class ChannelToForwardedUsers(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = safe_get_identifier(request, "properties.channel")
        if not identifier:
            response.addUIMessage("No channel specified", messageType="PartialError")
            return

        try:
            users_with_avatars, authors = run_telegram(fetch_forwarded_users_and_authors(identifier))

            for author_name in authors:
                entity = response.addEntity("interlinked.telegram.Author", value=author_name)
                entity.setLinkThickness(2)

            for user, avatar_b64 in users_with_avatars:
                entity = process_profile_entity(user, avatar_b64=avatar_b64)
                entity.setLinkThickness(2)
                response.entities.append(entity)

        except Exception as e:
            response.addUIMessage(f"Error fetching forwarded users: {e}", messageType="PartialError")
