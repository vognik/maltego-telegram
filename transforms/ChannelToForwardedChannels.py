from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from settings import app, loop, limit
from extensions import registry

from utils import message_is_forwarded_from_another_chat, fetch_web_info


async def fetch_forwarded_channels(username: str):
    channels = []

    async with app:
        async for message in app.get_chat_history(username, limit=limit):
            if not message_is_forwarded_from_another_chat(message, username):
                continue

            channels.append(message.forward_from_chat)

    return channels


@registry.register_transform(
    display_name="To Forwarded Channels",
    input_entity="interlinked.telegram.Channel",
    description="This Transform receives all channels whose posts have been forwarded by this channel",
    output_entities=["interlinked.telegram.Channel"],
)
class ChannelToForwardedChannels(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = request.getProperty("properties.channel")
        channels = loop.run_until_complete(fetch_forwarded_channels(username))

        for channel in channels:
            identity = channel.username if channel.username else channel.id

            entity = response.addEntity("interlinked.telegram.Channel", value=identity)
            entity.addProperty("properties.title", value=channel.title)
            entity.addProperty("properties.id", value=channel.id)

            if channel.username:
                photo = fetch_web_info(channel.username)["photo"]
                entity.addProperty("properties.photo", value=photo)

            entity.setLinkThickness(2)
