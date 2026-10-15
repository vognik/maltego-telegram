"""
Transform: Bot Referral to Telegram Profile
Extracts a Telegram profile ID from a bot referral link (e.g. https://t.me/bot?start=invite_12345678)
and resolves the owner's Telegram profile via MTProto and the configured user_lookup_bot.
"""

import logging
import re
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from maltego_trx.transform import DiscoverableTransform
from pyrogram.types import User

from client import get_client, run_telegram
from extensions import registry
from settings import USER_LOOKUP_BOT
from utils import (
    download_avatar_b64,
    extract_username_from_text,
    process_profile_entity,
    query_bot_dialog,
    query_inline_bot,
)

logger = logging.getLogger("maltego_telegram.BotReferralToProfile")


def extract_profile_id_from_referral(url_or_code: str) -> Optional[int]:
    """
    Extracts a numeric Telegram profile ID from a referral URL or referral code.
    Supports:
      - https://t.me/example_bot?start=invite_12345678
      - https://t.me/example_bot?start=12345678
      - https://t.me/example_bot?start=ref_12345678
      - https://t.me/example_bot/app?startapp=12345678
      - tg://resolve?domain=example_bot&start=invite_12345678
      - Raw codes: invite_12345678, ref-12345678, 12345678
    """
    if not url_or_code:
        return None

    text = str(url_or_code).strip()

    # 1. If it's a URL, extract the referral query param value first
    target = text
    if "?" in text:
        try:
            parsed = urlparse(text)
            qs = parse_qs(parsed.query)
            for p in ("start", "startapp", "startgroup", "startattach", "ref", "referral", "code"):
                vals = qs.get(p)
                if vals and vals[0].strip():
                    target = vals[0].strip()
                    break
        except Exception:
            target = text

    # 2. Look for common referral prefix followed by 5 to 12 digits
    prefix_match = re.search(
        r"(?:invite|ref|user|id|u|r|c)[_\-:]?(\d{5,12})\b",
        target,
        re.IGNORECASE,
    )
    if prefix_match:
        try:
            val = int(prefix_match.group(1))
            if val > 0:
                return val
        except ValueError:
            pass

    # 3. Look for standalone 5 to 12 digit integer
    digits_match = re.search(r"\b(\d{5,12})\b", target)
    if digits_match:
        try:
            val = int(digits_match.group(1))
            if val > 0:
                return val
        except ValueError:
            pass

    # 4. Fallback: match any contiguous 5 to 12 digit sequence
    any_digits = re.findall(r"\d{5,12}", target)
    if any_digits:
        try:
            val = int(any_digits[0])
            if val > 0:
                return val
        except ValueError:
            pass

    return None


async def resolve_profile_from_referral(
    url_or_code: str,
) -> Tuple[User, Optional[str], int]:
    """
    Extracts profile ID from referral link and resolves user profile
    via MTProto and configured user_lookup_bot.
    Returns (User, avatar_b64, profile_id).
    """
    client = get_client()
    profile_id = extract_profile_id_from_referral(url_or_code)
    if not profile_id:
        raise ValueError(f"No valid Telegram profile ID found in '{url_or_code}'")

    # 1. Attempt direct MTProto resolution (if cached or known in session)
    try:
        user = await client.get_users(profile_id)
        if user and not user.is_deleted:
            avatar_b64 = await download_avatar_b64(client, user)
            return user, avatar_b64, profile_id
    except Exception:
        pass

    # 2. Query configured user lookup bot via inline query
    if USER_LOOKUP_BOT:
        try:
            inline_results = await query_inline_bot(client, USER_LOOKUP_BOT, str(profile_id))
            if inline_results:
                for res in inline_results:
                    msg_text = getattr(res.send_message, "message", "") or ""
                    desc = getattr(res, "description", "") or ""
                    title = getattr(res, "title", "") or ""

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
                                return resolved_user, avatar_b64, profile_id
                        except Exception:
                            dummy = User(
                                id=profile_id,
                                username=found_username,
                                first_name=found_username,
                            )
                            avatar_b64 = await download_avatar_b64(client, dummy)
                            return dummy, avatar_b64, profile_id
        except Exception:
            pass

        # 3. Fallback: try direct bot message dialog if inline query yielded no username
        try:
            reply = await query_bot_dialog(client, USER_LOOKUP_BOT, str(profile_id), timeout=8.0)
            if reply and reply.text:
                found_username = extract_username_from_text(reply.text)
                if found_username:
                    try:
                        resolved_user = await client.get_users(found_username)
                        if resolved_user:
                            avatar_b64 = await download_avatar_b64(client, resolved_user)
                            return resolved_user, avatar_b64, profile_id
                    except Exception:
                        dummy = User(
                            id=profile_id,
                            username=found_username,
                            first_name=found_username,
                        )
                        avatar_b64 = await download_avatar_b64(client, dummy)
                        return dummy, avatar_b64, profile_id
        except Exception:
            pass

    # 4. Fallback to minimal User with extracted profile ID
    dummy_user = User(id=profile_id, first_name=f"User #{profile_id}")
    avatar_b64 = await download_avatar_b64(client, dummy_user)
    return dummy_user, avatar_b64, profile_id


@registry.register_transform(
    display_name="To Telegram Profile",
    input_entity="maltego.URL",
    description="Resolves Telegram profile from bot referral ID via MTProto user lookup bot",
    output_entities=["interlinked.telegram.UserProfile"],
)
class BotReferralToProfile(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        raw_input = (
            request.getProperty("properties.code")
            or request.getProperty("url")
            or request.getProperty("properties.url")
            or request.Value
        )
        if not raw_input:
            response.addUIMessage("No URL or referral code specified", messageType="PartialError")
            return

        profile_id = extract_profile_id_from_referral(raw_input)
        if not profile_id:
            response.addUIMessage(
                f"No profile ID could be extracted from: {raw_input}",
                messageType="PartialError",
            )
            return

        try:
            user, avatar_b64, uid = run_telegram(resolve_profile_from_referral(raw_input))
            entity = process_profile_entity(user, avatar_b64=avatar_b64)
            entity.addProperty("properties.extracted_id", value=str(uid))
            entity.addProperty("properties.source_referral", value=str(raw_input))
            entity.setLinkColor("0xB5E61D")
            entity.setLinkThickness(2)
            response.entities.append(entity)
        except Exception as e:
            response.addUIMessage(f"Error resolving referral profile: {e}", messageType="PartialError")
