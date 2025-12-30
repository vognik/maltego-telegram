from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from settings import app, loop, limit
from extensions import registry

from utils import message_is_forwarded_from_another_chat


async def fetch_authors(username: str):
    authors = []

    async with app:
        async for message in app.get_chat_history(username, limit=limit):
            if (
                message_is_forwarded_from_another_chat(message, username)
                or not message.author_signature
            ):
                continue

            authors.append(message.author_signature)

    return authors


@registry.register_transform(
    display_name="To Authors",
    input_entity="interlinked.telegram.Channel",
    description="This Transform finds authors who published posts",
    output_entities=["interlinked.telegram.Author"],
)
class ChannelToAuthors(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = request.getProperty("properties.channel")
        authors = loop.run_until_complete(fetch_authors(username))

        for author in authors:
            entity = response.addEntity("interlinked.telegram.Author", value=author)
            entity.setLinkThickness(2)
