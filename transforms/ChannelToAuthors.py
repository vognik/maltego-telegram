"""
Transform: Channel to Authors
Extracts authors of published posts in a Telegram channel.
"""

from typing import List
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform

from extensions import registry
from client import run_telegram, get_client
from settings import LIMIT
from utils import safe_get_identifier, normalize_identifier, message_is_forwarded_from_another_chat


async def fetch_authors(identifier: str) -> List[str]:
    client = get_client()
    clean_id = normalize_identifier(identifier)
    seen_authors = set()
    authors = []

    async for message in client.get_chat_history(clean_id, limit=LIMIT):
        if message_is_forwarded_from_another_chat(message, clean_id) or not message.author_signature:
            continue

        sig = message.author_signature.strip()
        if sig and sig not in seen_authors:
            seen_authors.add(sig)
            authors.append(sig)

    return authors


@registry.register_transform(
    display_name="To Authors",
    input_entity="interlinked.telegram.Channel",
    description="Finds author signatures of published posts in a Telegram channel",
    output_entities=["interlinked.telegram.Author"],
)
class ChannelToAuthors(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = safe_get_identifier(request, "properties.channel")
        if not identifier:
            response.addUIMessage("No channel specified", messageType="PartialError")
            return

        try:
            authors = run_telegram(fetch_authors(identifier))
            for author in authors:
                entity = response.addEntity("interlinked.telegram.Author", value=author)
                entity.setLinkThickness(2)
        except Exception as e:
            response.addUIMessage(f"Error fetching channel authors: {e}", messageType="PartialError")
