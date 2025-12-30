from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from settings import app, loop
from extensions import registry
from utils import fetch_web_info


async def fetch_linked_group(username: str):
    async with app:
        channel_info = await app.get_chat(username)

    if channel_info.linked_chat:
        return channel_info.linked_chat

    return


@registry.register_transform(
    display_name="To Linked Group",
    input_entity="interlinked.telegram.Channel",
    description="This Transform finds the linked group",
    output_entities=["interlinked.telegram.Group"],
)
class ChannelToGroup(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = request.getProperty("properties.channel")
        linked_group = loop.run_until_complete(fetch_linked_group(username))

        if linked_group:
            identity = (
                linked_group.username if linked_group.username else linked_group.id
            )

            group_entity = response.addEntity(
                "interlinked.telegram.Group", value=identity
            )
            group_entity.addProperty("properties.title", value=linked_group.title)

            photo = fetch_web_info(linked_group.username)["photo"]
            group_entity.addProperty("properties.photo", value=photo)

            group_entity.setLinkThickness(2)
