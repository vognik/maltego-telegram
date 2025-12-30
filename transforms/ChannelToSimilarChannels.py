from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from settings import app, loop, threads
from extensions import registry

from utils import (
    fetch_web_info,
    create_maltego_entity,
)
import multiprocessing


async def fetch_similar_channels(username: str):
    async with app:
        return await app.get_similar_channels(username)


def assign_first_username(channels):
    for channel in channels:
        if channel.usernames:
            channel.username = channel.usernames[0].username

    return channels


@registry.register_transform(
    display_name="To Similar Channels",
    input_entity="interlinked.telegram.Channel",
    description="This transform is designed to identify similarly themed public channels by analyzing similarities in their subscriber bases",
    output_entities=["interlinked.telegram.Channel"],
)
class ChannelToSimilarChannels(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = request.getProperty("properties.channel")
        channels = loop.run_until_complete(fetch_similar_channels(username))
        channels = assign_first_username(channels)

        with multiprocessing.Pool(processes=threads) as pool:
            web_info = pool.map(fetch_web_info, [i.username for i in channels])

        for i, channel in enumerate(channels):
            entity = create_maltego_entity("interlinked.telegram.Channel", channel)
            entity.addProperty("properties.photo", value=web_info[i]["photo"])
            response.entities.append(entity)
