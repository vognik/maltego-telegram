from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from settings import app, loop, limit
from extensions import registry

from utils import media_fetcher


async def fetch_stickers(username):
    sticker_sets = []
    unique_set_names = set()

    async with app:
        async for message in app.get_chat_history(username, limit=limit):
            if (
                message.sticker is not None
                and message.sticker.set_name not in unique_set_names
            ):
                unique_set_names.add(message.sticker.set_name)
                sticker_sets.append(message.sticker)

    return sticker_sets


@registry.register_transform(
    display_name="To Sticker Sets",
    input_entity="interlinked.telegram.Channel",
    description="Extracts all sticker sets from a Telegram channel",
    output_entities=["interlinked.telegram.StickerSet"],
)
class ChannelToStickerSet(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = request.getProperty("properties.channel")
        sticker_sets = loop.run_until_complete(fetch_stickers(username))

        for sticker_set in sticker_sets:
            stickerset_entity = response.addEntity(
                "interlinked.telegram.StickerSet", value=sticker_set.set_name
            )
            stickerset_entity.addProperty(
                "properties.title", value=sticker_set.set_name
            )

            thumbnail = media_fetcher.get_media_preview_url(sticker_set.set_name)
            stickerset_entity.addProperty("properties.thumbnail", value=thumbnail)

            stickerset_entity.setLinkColor("0x99D9EA")
            stickerset_entity.setLinkThickness(2)
