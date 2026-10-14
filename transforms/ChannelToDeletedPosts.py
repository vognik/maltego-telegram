"""
Transform: Channel to Deleted Posts
Detects gaps in Telegram message IDs and generates links to view archived posts on tgstat.
"""

from typing import List, Tuple
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform

from extensions import registry
from client import run_telegram, get_client
from settings import LIMIT
from utils import safe_get_identifier, normalize_identifier


async def find_missing_post_ids(identifier: str) -> Tuple[str, List[int]]:
    client = get_client()
    clean_id = normalize_identifier(identifier)
    ids = []

    async for message in client.get_chat_history(clean_id, limit=LIMIT):
        ids.append(message.id)

    if len(ids) < 2:
        return clean_id, []

    # Detect missing sequential numbers between min and max retrieved IDs
    full_range = set(range(min(ids), max(ids) + 1))
    missing = sorted(full_range.difference(ids))
    return clean_id, missing


@registry.register_transform(
    display_name="To Deleted Posts",
    input_entity="interlinked.telegram.Channel",
    description="Finds deleted posts by detecting ID gaps and generates archive links",
    output_entities=["maltego.URL"],
)
class ChannelToDeletedPosts(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = safe_get_identifier(request, "properties.channel")
        if not identifier:
            response.addUIMessage("No channel specified", messageType="PartialError")
            return

        try:
            clean_id, missing_ids = run_telegram(find_missing_post_ids(identifier))
            for post_id in missing_ids:
                link = f"https://tgstat.ru/channel/{clean_id}/{post_id}"
                entity = response.addEntity("maltego.URL", value=str(post_id))
                entity.addProperty("url", value=link)
                entity.addProperty("title", value=f"Deleted Post #{post_id}")
        except Exception as e:
            response.addUIMessage(f"Error finding deleted posts: {e}", messageType="PartialError")
