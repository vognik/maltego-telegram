from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from settings import app, loop, limit
from extensions import registry

from pyrogram.enums import MessageEntityType

from utils import media_fetcher, message_is_forwarded_from_another_chat


async def collect_available_reactions(username):
    reactions = []

    async with app:
        chat_info = await app.get_chat(username)

    if chat_info.available_reactions:
        reactions = chat_info.available_reactions.reactions
        if reactions is None:
            return []

    return [i.custom_emoji_id for i in reactions] if reactions else []


async def collect_emoji_ids(username):
    emoji_ids = set()

    async with app:
        async for message in app.get_chat_history(username, limit=limit):
            if message_is_forwarded_from_another_chat(message, username):
                continue

            entities = message.entities or []
            caption_entities = message.caption_entities or []

            for entity in entities + caption_entities:
                if entity.type == MessageEntityType.CUSTOM_EMOJI and hasattr(
                    entity, "custom_emoji_id"
                ):
                    emoji_ids.add(entity.custom_emoji_id)

    available_reactions = await collect_available_reactions(username)
    emoji_ids.update(available_reactions)

    return list(emoji_ids)


async def fetch_emoji_info(emoji_ids):
    emoji_sets = []
    batch_size = 200
    current_batch = []

    async with app:
        for custom_emoji_id in emoji_ids:
            if custom_emoji_id is not None:
                current_batch.append(custom_emoji_id)

            if len(current_batch) == batch_size:
                emoji_info_list = await app.get_custom_emoji_stickers(
                    custom_emoji_ids=current_batch
                )
                emoji_sets.extend(emoji_info_list)
                current_batch.clear()

        if current_batch:
            emoji_info_list = await app.get_custom_emoji_stickers(
                custom_emoji_ids=current_batch
            )
            emoji_sets.extend(emoji_info_list)

    emoji_sets = remove_duplicates(emoji_sets)

    return emoji_sets


def remove_duplicates(emoji_sets):
    seen_set_names = set()
    unique_emoji_sets = []

    for emoji in emoji_sets:
        if emoji.set_name not in seen_set_names:
            seen_set_names.add(emoji.set_name)
            unique_emoji_sets.append(emoji)

    return unique_emoji_sets


@registry.register_transform(
    display_name="To Emoji Sets",
    input_entity="interlinked.telegram.Channel",
    description="Extracts all emoji sets from a Telegram channel",
    output_entities=["interlinked.telegram.StickerSet"],
)
class ChannelToEmojiSet(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = request.getProperty("properties.channel")
        emoji_sets = loop.run_until_complete(collect_emoji_ids(username))
        emojis_info = loop.run_until_complete(fetch_emoji_info(emoji_sets))

        for emoji_set in emojis_info:
            emoji_entity = response.addEntity(
                "interlinked.telegram.StickerSet", value=emoji_set.set_name
            )

            thumbnail = media_fetcher.get_media_preview_url(
                emoji_set.set_name,
                file_id=emoji_set.thumbs[0].file_id,
                media_type="emoji",
            )
            emoji_entity.addProperty("properties.thumbnail", value=thumbnail)
            emoji_entity.addProperty("properties.title", value=emoji_set.set_name)

            emoji_entity.setLinkColor("0xFFAEC9")
            emoji_entity.setLinkThickness(2)
