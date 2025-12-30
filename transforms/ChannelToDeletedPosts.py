from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from settings import app, loop, limit
from extensions import registry


async def find_missing_post_ids(username: str) -> list[int]:
    ids = []

    async with app:
        async for message in app.get_chat_history(username, limit=limit):
            ids.append(message.id)

    if not ids:
        return []

    full_range = set(range(min(ids), max(ids) + 1))
    missing_numbers = sorted(full_range.difference(ids))

    return missing_numbers


@registry.register_transform(
    display_name="To Deleted Posts",
    input_entity="interlinked.telegram.Channel",
    description="This Transform finds deleted posts and generates links to view them",
    output_entities=["maltego.URL"],
)
class ChannelToDeletedPosts(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = request.getProperty("properties.channel")
        ids = loop.run_until_complete(find_missing_post_ids(username))

        for post_id in ids:
            link = f"https://tgstat.ru/channel/{username}/{post_id}"
            entity = response.addEntity("maltego.URL", value=str(post_id))
            entity.addProperty("url", value=link)
            entity.addProperty("title", value=post_id)
