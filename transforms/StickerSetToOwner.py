"""
Transform: Sticker Set to Owner
De-anonymizes the creator of a Telegram sticker or emoji pack by extracting their UID
from the pack's 64-bit ID, then resolving the UID to a user profile via MTProto.
Bot username is loaded strictly from config.ini ([bots] user_lookup_bot).
100% MTProto, zero hardcoded bot logins.
"""

from typing import Optional, Tuple
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.raw import functions, types as raw_types
from pyrogram.types import User

from extensions import registry
from client import run_telegram, get_client
from settings import USER_LOOKUP_BOT
from utils import (
    safe_get_identifier,
    normalize_identifier,
    download_avatar_b64,
    process_profile_entity,
    query_inline_bot,
    extract_username_from_text,
)


async def fetch_sticker_set_owner(short_name: str) -> Tuple[User, Optional[str]]:
    client = get_client()
    clean_name = normalize_identifier(short_name)

    # 1. Fetch sticker set via MTProto
    sticker_set = await client.invoke(
        functions.messages.GetStickerSet(
            stickerset=raw_types.InputStickerSetShortName(short_name=clean_name),
            hash=0,
        )
    )

    if not sticker_set or not getattr(sticker_set, "set", None):
        raise ValueError(f"Sticker pack '{clean_name}' not found")

    # 2. Extract owner UID using 32-bit right binary shift
    owner_id = sticker_set.set.id >> 32

    # 3. Attempt direct MTProto user resolution
    try:
        user = await client.get_users(owner_id)
        if user and not user.is_deleted:
            avatar_b64 = await download_avatar_b64(client, user)
            return user, avatar_b64
    except Exception:
        pass

    # 4. If not cached locally, query the configured user lookup bot
    if USER_LOOKUP_BOT:
        try:
            inline_results = await query_inline_bot(client, USER_LOOKUP_BOT, str(owner_id))
            if inline_results:
                for res in inline_results:
                    msg_text = getattr(res.send_message, "message", "") or ""
                    desc = getattr(res, "description", "") or ""
                    title = getattr(res, "title", "") or ""

                    # Extract username matching login regex from message text or description
                    found_username = (
                        extract_username_from_text(msg_text)
                        or extract_username_from_text(desc)
                        or extract_username_from_text(title)
                    )

                    if found_username:
                        try:
                            resolved_user = await client.get_users(found_username)
                            if resolved_user:
                                avatar_b64 = await download_avatar_b64(client, resolved_user)
                                return resolved_user, avatar_b64
                        except Exception:
                            # If get_users fails, create minimal User with extracted username and known ID
                            dummy = User(id=owner_id, username=found_username, first_name=found_username)
                            avatar_b64 = await download_avatar_b64(client, dummy)
                            return dummy, avatar_b64
        except Exception:
            pass

    # Fallback to minimal User with known UID
    dummy_user = User(id=owner_id, first_name=f"User #{owner_id}")
    avatar_b64 = await download_avatar_b64(client, dummy_user)
    return dummy_user, avatar_b64


@registry.register_transform(
    display_name="To Sticker Set Owner",
    input_entity="interlinked.telegram.StickerSet",
    description="De-anonymizes the owner of a sticker/emoji pack by extracting UID from pack ID via MTProto",
    output_entities=["interlinked.telegram.UserProfile"],
)
class StickerSetToOwner(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        short_name = safe_get_identifier(request, "properties.short_name")
        if not short_name:
            response.addUIMessage("No sticker set short name specified", messageType="PartialError")
            return

        try:
            owner, avatar_b64 = run_telegram(fetch_sticker_set_owner(short_name))
            entity = process_profile_entity(owner, avatar_b64=avatar_b64)
            entity.setLinkColor("0xB5E61D")
            entity.setLinkThickness(2)
            response.entities.append(entity)
        except Exception as e:
            response.addUIMessage(f"Error finding sticker set owner: {e}", messageType="PartialError")
