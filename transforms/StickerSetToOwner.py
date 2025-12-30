from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from settings import app, loop
from extensions import registry
from utils import fetch_web_info, get_default_photo_b64

from pyrogram.raw import types, functions
from pyrogram.types import User

import re
import contextlib


async def fetch_sticker_set_owner(short_name: str):
    async with app:
        sticker_set = await app.invoke(
            functions.messages.GetStickerSet(
                stickerset=types.InputStickerSetShortName(short_name=short_name), hash=0
            ),
        )

        owner_id = sticker_set.set.id >> 32

        with contextlib.suppress(Exception):
            if owner := await app.get_users(owner_id):
                return owner

        try:
            inline_search = await app.get_inline_bot_results(
                "tgdb_search_bot", str(owner_id)
            )
        except Exception:
            return User(id=owner_id)

        if inline_results := inline_search.results:
            message_text = inline_results[0].send_message.message
            username_match = re.search(r"(@\S+)", message_text)
            if username_match:
                username = username_match[0]
                with contextlib.suppress(Exception):
                    owner = await app.get_users(username)
                    return owner

        return User(id=owner_id)


@registry.register_transform(
    display_name="To Sticker Set Owner",
    input_entity="interlinked.telegram.StickerSet",
    description="This Transform finds the owner of the sticker set",
    output_entities=["interlinked.telegram.UserProfile"],
)
class StickerSetToOwner(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        short_name = request.getProperty("properties.short_name")

        owner = loop.run_until_complete(fetch_sticker_set_owner(short_name))

        stickerset_owner_entity = response.addEntity(
            "interlinked.telegram.UserProfile",
            value=owner.username if owner.username is not None else owner.id,
        )

        if owner.username is not None:
            owner_info = fetch_web_info(owner.username)
            stickerset_owner_entity.addProperty(
                "properties.photo", value=owner_info["photo"]
            )
            stickerset_owner_entity.addProperty(
                "properties.full_name",
                value=owner_info["full_name"]
                if owner_info["full_name"]
                else owner.username,
            )
        else:
            stickerset_owner_entity.addProperty("properties.id", value=owner.id)
            stickerset_owner_entity.addProperty("properties.full_name", value=owner.id)
            stickerset_owner_entity.addProperty(
                "base64", value=get_default_photo_b64(owner.id)
            )

        stickerset_owner_entity.setLinkColor("0xB5E61D")
        stickerset_owner_entity.setLinkThickness(2)
