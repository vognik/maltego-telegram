from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from settings import app, loop, limit
from extensions import registry
from pyrogram.types import User

from utils import create_maltego_entity, fetch_web_info


async def find_forwarded_messages_from_users(username):
    messages = []
    async with app:
        async for message in app.get_chat_history(username, limit=limit):
            if message.forward_sender_name is not None or isinstance(
                message.forward_from, User
            ):
                messages.append(message)

    return messages


def get_unique_forward_users(messages):
    unique_forward_users = []
    seen_ids = set()

    for message in messages:
        if message.forward_from is not None and message.forward_from.id not in seen_ids:
            unique_forward_users.append(message.forward_from)
            seen_ids.add(message.forward_from.id)

    return unique_forward_users


@registry.register_transform(
    display_name="To Forwarded Users",
    input_entity="interlinked.telegram.Channel",
    description="This Transform receives all users mentioned by this channel",
    output_entities=["interlinked.telegram.UserProfile", "interlinked.telegram.Author"],
)
class ChannelToForwardedUsers(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = request.getProperty("properties.channel")
        messages = loop.run_until_complete(find_forwarded_messages_from_users(username))

        authors = list(
            {
                message.forward_sender_name
                for message in messages
                if message.forward_sender_name is not None
            }
        )
        users = get_unique_forward_users(messages)

        for author in authors:
            entity = response.addEntity("interlinked.telegram.Author", value=author)
            entity.setLinkThickness(2)

        for user in users:
            entity = create_maltego_entity("interlinked.telegram.UserProfile", user)

            if user.username:
                photo = fetch_web_info(user.username)["photo"]
                entity.addProperty("properties.photo", value=photo)

            entity.setLinkThickness(2)
            response.entities.append(entity)
