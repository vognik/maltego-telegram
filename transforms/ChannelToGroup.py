"""
Transform: Channel to Linked Group
Finds the discussion supergroup or chat linked to a Telegram channel.
"""

from typing import Optional, Tuple
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.types import Chat

from extensions import registry
from client import run_telegram, get_client
from utils import safe_get_identifier, normalize_identifier, download_avatar_b64


async def fetch_linked_group(identifier: str) -> Optional[Tuple[Chat, str]]:
    client = get_client()
    clean_id = normalize_identifier(identifier)

    try:
        chat = await client.get_chat(clean_id)
        if getattr(chat, "linked_chat", None):
            linked = chat.linked_chat
            avatar_b64 = await download_avatar_b64(client, linked)
            return linked, avatar_b64
    except Exception:
        pass
    return None


@registry.register_transform(
    display_name="To Linked Group",
    input_entity="interlinked.telegram.Channel",
    description="Finds the discussion group linked to a Telegram channel",
    output_entities=["interlinked.telegram.Group"],
)
class ChannelToGroup(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = safe_get_identifier(request, "properties.channel")
        if not identifier:
            response.addUIMessage("No channel specified", messageType="PartialError")
            return

        try:
            result = run_telegram(fetch_linked_group(identifier))
            if result:
                linked_chat, avatar_b64 = result
                identity = linked_chat.username or str(linked_chat.id)
                entity = response.addEntity("interlinked.telegram.Group", value=identity)
                entity.addProperty("properties.id", value=str(linked_chat.id))
                if linked_chat.title:
                    entity.addProperty("properties.title", value=linked_chat.title)
                if linked_chat.username:
                    entity.addProperty("properties.username", value=linked_chat.username)
                if avatar_b64:
                    entity.addProperty("base64", value=avatar_b64)
                entity.setLinkThickness(2)
            else:
                response.addUIMessage("No linked group found for this channel", messageType="Inform")
        except Exception as e:
            response.addUIMessage(f"Error fetching linked group: {e}", messageType="PartialError")
