"""
Transform: Channel to Bot Referral Links
Extracts referral links to Telegram bots (e.g. https://t.me/bot?start=ref_id)
from Telegram channel posts, text hyperlinks, and inline keyboard buttons.
"""

from dataclasses import dataclass
import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from maltego_trx.transform import DiscoverableTransform
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from client import get_client, run_telegram
from extensions import registry
from settings import LIMIT
from utils import normalize_identifier, safe_get_identifier

logger = logging.getLogger("maltego_telegram.ChannelToBotReferrals")

# Regex to find potential Telegram URL strings in text
URL_REGEX = re.compile(
    r'(?:https?://|tg://|(?:t\.me|telegram\.me|telegram\.dog)/)[^\s<>"\'\)\(\]\[]+',
    re.IGNORECASE,
)

# Deep linking query parameters used for Telegram bots and referral tracking
REFERRAL_PARAMS = ("start", "startapp", "startgroup", "startattach", "ref", "referral")

# Reserved path prefixes on t.me that are NOT bots
RESERVED_PATHS = {
    "s",
    "c",
    "joinchat",
    "addstickers",
    "addemoji",
    "addtheme",
    "share",
    "login",
    "iv",
    "contact",
    "invoice",
    "socks",
    "proxy",
    "setlanguage",
}


@dataclass
class ReferralMatch:
    url: str
    original_url: str
    bot_username: str
    referral_param: str
    referral_code: str


@dataclass
class ExtractedReferral:
    match: ReferralMatch
    button_text: Optional[str] = None
    link_text: Optional[str] = None


@dataclass
class ReferralLinkItem:
    url: str
    bot_username: str
    referral_param: str
    referral_code: str
    first_post_id: int
    last_post_id: int
    mention_count: int
    post_urls: List[str]
    button_texts: List[str]
    link_texts: List[str]
    is_forwarded: bool


def extract_text_slice(text: Optional[str], offset: int, length: int) -> Optional[str]:
    """
    Extracts substring for a Telegram MessageEntity.
    Handles UTF-16 code units used by MTProto entity offsets.
    """
    if not text or offset < 0 or length <= 0:
        return None
    try:
        encoded = text.encode("utf-16-le")
        start = offset * 2
        end = (offset + length) * 2
        res = encoded[start:end].decode("utf-16-le", errors="replace").strip()
        return res if res else None
    except Exception:
        fallback = text[offset : offset + length].strip()
        return fallback if fallback else None


def parse_bot_referral(raw_url: str) -> Optional[ReferralMatch]:
    """
    Parses a URL and determines if it is a Telegram bot referral link.
    Supports:
      - https://t.me/sample_bot?start=invite_12345678
      - https://telegram.me/bot?start=...
      - https://t.me/bot/app?startapp=...
      - tg://resolve?domain=bot&start=...
      - Schemeless t.me/bot?start=...
    """
    if not raw_url:
        return None

    clean_url = raw_url.strip().rstrip(".,;:!?'\")>")
    if not clean_url:
        return None

    # Handle tg:// protocol: tg://resolve?domain=<bot>&start=<ref>
    if clean_url.startswith("tg://"):
        try:
            parsed = urlparse(clean_url)
            qs = parse_qs(parsed.query)
            domain_list = qs.get("domain", [])
            bot_username = domain_list[0].strip().lstrip("@") if domain_list else None
            if not bot_username or bot_username.lower() in RESERVED_PATHS:
                return None

            for p in REFERRAL_PARAMS:
                vals = qs.get(p)
                if vals and vals[0].strip():
                    ref_param = p
                    ref_code = vals[0].strip()
                    canonical_url = f"https://t.me/{bot_username}?{ref_param}={ref_code}"
                    return ReferralMatch(
                        url=canonical_url,
                        original_url=clean_url,
                        bot_username=bot_username,
                        referral_param=ref_param,
                        referral_code=ref_code,
                    )
        except Exception:
            return None
        return None

    # Ensure http/https scheme for parsing
    has_scheme = clean_url.startswith("http://") or clean_url.startswith("https://")
    url_to_parse = clean_url if has_scheme else ("https://" + clean_url)

    try:
        parsed = urlparse(url_to_parse)
    except Exception:
        return None

    netloc = parsed.netloc.lower().split(":")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]

    if netloc not in ("t.me", "telegram.me", "telegram.dog"):
        return None

    path = parsed.path.strip("/")
    if not path:
        return None

    segments = path.split("/")
    raw_username = segments[0]

    # Ignore reserved prefixes or private invite links (+...)
    if raw_username.startswith("+") or raw_username.lower() in RESERVED_PATHS:
        return None

    # Telegram bot username format: alphanumeric + underscore, 3-32 chars
    if not re.match(r"^[A-Za-z0-9_]{3,32}$", raw_username):
        return None

    bot_username = raw_username

    # Parse query parameters
    qs = parse_qs(parsed.query)
    ref_param = None
    ref_code = None
    for p in REFERRAL_PARAMS:
        vals = qs.get(p)
        if vals and vals[0].strip():
            ref_param = p
            ref_code = vals[0].strip()
            break

    if not ref_param or not ref_code:
        return None

    # Construct canonical URL
    if len(segments) > 1 and ref_param in ("startapp", "startattach"):
        canonical_url = f"https://t.me/{bot_username}/{segments[1]}?{ref_param}={ref_code}"
    else:
        canonical_url = f"https://t.me/{bot_username}?{ref_param}={ref_code}"

    return ReferralMatch(
        url=canonical_url,
        original_url=clean_url if has_scheme else f"https://{clean_url}",
        bot_username=bot_username,
        referral_param=ref_param,
        referral_code=ref_code,
    )


def extract_referrals_from_message(
    message: Message,
    clean_channel_id: str,
) -> List[ExtractedReferral]:
    """
    Extracts all referral links and their associated button/anchor labels from a Message.
    Returns a list of ExtractedReferral objects with button_text and link_text.
    """
    found: List[ExtractedReferral] = []
    seen_urls_in_msg = set()

    def _consider(
        candidate_url: Optional[str],
        button_text: Optional[str] = None,
        link_text: Optional[str] = None,
    ):
        if not candidate_url:
            return
        match = parse_bot_referral(candidate_url)
        if not match:
            return

        if match.url in seen_urls_in_msg:
            # Enrich existing referral if we found button_text or link_text
            for item in found:
                if item.match.url == match.url:
                    if button_text and not item.button_text:
                        item.button_text = button_text
                    if link_text and not item.link_text:
                        item.link_text = link_text
            return

        seen_urls_in_msg.add(match.url)
        found.append(
            ExtractedReferral(
                match=match,
                button_text=button_text,
                link_text=link_text,
            )
        )

    # 1. Inline keyboard buttons (extremely common for referral bots!)
    markup = getattr(message, "reply_markup", None)
    if markup and getattr(markup, "inline_keyboard", None):
        for row in markup.inline_keyboard:
            for btn in row:
                btn_url = getattr(btn, "url", None)
                btn_text = getattr(btn, "text", None)
                _consider(btn_url, button_text=btn_text)

                web_app = getattr(btn, "web_app", None)
                if web_app and getattr(web_app, "url", None):
                    _consider(web_app.url, button_text=btn_text)

    # 2. Text entities (MessageEntityType.TEXT_LINK and URL) in message.text
    if getattr(message, "entities", None) and getattr(message, "text", None):
        for ent in message.entities:
            if ent.type == MessageEntityType.TEXT_LINK and getattr(ent, "url", None):
                anchor = extract_text_slice(message.text, ent.offset, ent.length)
                _consider(ent.url, link_text=anchor)
            elif ent.type == MessageEntityType.URL and getattr(ent, "url", None):
                _consider(ent.url, None)

    # 3. Text entities in message.caption
    if getattr(message, "caption_entities", None) and getattr(message, "caption", None):
        for ent in message.caption_entities:
            if ent.type == MessageEntityType.TEXT_LINK and getattr(ent, "url", None):
                anchor = extract_text_slice(message.caption, ent.offset, ent.length)
                _consider(ent.url, link_text=anchor)
            elif ent.type == MessageEntityType.URL and getattr(ent, "url", None):
                _consider(ent.url, None)

    # 4. Regex on raw message text and caption
    for text_source in (getattr(message, "text", None), getattr(message, "caption", None)):
        if not text_source:
            continue
        for m in URL_REGEX.finditer(text_source):
            _consider(m.group(0), None)

    # 5. Web page preview if available
    web_page = getattr(message, "web_page", None)
    if web_page and getattr(web_page, "url", None):
        _consider(web_page.url, link_text=getattr(web_page, "title", None))

    return found


async def fetch_bot_referrals(identifier: str) -> List[ReferralLinkItem]:
    """
    Scans recent channel messages for Telegram bot referral links.
    Aggregates metrics: mention counts, post IDs, button texts, link texts.
    """
    client = get_client()
    clean_id = normalize_identifier(identifier)
    target_chat = int(clean_id) if clean_id.lstrip("-").isdigit() else clean_id

    referrals_map: Dict[str, ReferralLinkItem] = {}

    async for message in client.get_chat_history(target_chat, limit=LIMIT):
        extracted = extract_referrals_from_message(message, clean_id)
        if not extracted:
            continue

        is_fwd = bool(getattr(message, "forward_from_chat", None) or getattr(message, "forward_from", None))
        post_url = f"https://t.me/{clean_id}/{message.id}"

        for item in extracted:
            key = item.match.url
            if key not in referrals_map:
                referrals_map[key] = ReferralLinkItem(
                    url=item.match.url,
                    bot_username=item.match.bot_username,
                    referral_param=item.match.referral_param,
                    referral_code=item.match.referral_code,
                    first_post_id=message.id,
                    last_post_id=message.id,
                    mention_count=1,
                    post_urls=[post_url],
                    button_texts=[item.button_text] if item.button_text else [],
                    link_texts=[item.link_text] if item.link_text else [],
                    is_forwarded=is_fwd,
                )
            else:
                ref_item = referrals_map[key]
                ref_item.mention_count += 1
                ref_item.first_post_id = min(ref_item.first_post_id, message.id)
                ref_item.last_post_id = max(ref_item.last_post_id, message.id)
                if post_url not in ref_item.post_urls:
                    ref_item.post_urls.append(post_url)
                if item.button_text and item.button_text not in ref_item.button_texts:
                    ref_item.button_texts.append(item.button_text)
                if item.link_text and item.link_text not in ref_item.link_texts:
                    ref_item.link_texts.append(item.link_text)

    return list(referrals_map.values())


@registry.register_transform(
    display_name="To Bot Referral Links",
    input_entity="interlinked.telegram.Channel",
    description="Finds bot referral links (e.g. t.me/...bot?start=...) in Telegram channel posts and buttons",
    output_entities=["maltego.URL"],
)
class ChannelToBotReferrals(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = safe_get_identifier(request, "properties.channel") or safe_get_identifier(
            request, "properties.username"
        )
        if not identifier:
            response.addUIMessage("No channel specified", messageType="PartialError")
            return

        try:
            referrals = run_telegram(fetch_bot_referrals(identifier))
            if not referrals:
                response.addUIMessage(f"No bot referral links found in {identifier}", messageType="Inform")
                return

            for ref in referrals:
                entity = response.addEntity("maltego.URL", value=ref.url)
                entity.addProperty("url", value=ref.url)

                title = f"@{ref.bot_username} ({ref.referral_code})"
                context_label = (
                    ref.button_texts[0]
                    if ref.button_texts
                    else (ref.link_texts[0] if ref.link_texts else None)
                )
                if context_label:
                    title += f" - {context_label[:30]}"
                entity.addProperty("title", value=title)

                entity.addProperty("properties.bot", value=f"@{ref.bot_username}")
                entity.addProperty("properties.param", value=ref.referral_param)
                entity.addProperty("properties.code", value=ref.referral_code)
                entity.addProperty("properties.mentions", value=str(ref.mention_count))
                entity.addProperty("properties.first_post_id", value=str(ref.first_post_id))
                entity.addProperty("properties.last_post_id", value=str(ref.last_post_id))
                if ref.post_urls:
                    entity.addProperty("properties.post_url", value=ref.post_urls[0])
                if ref.button_texts:
                    entity.addProperty("properties.button_text", value=" | ".join(ref.button_texts))
                if ref.link_texts:
                    entity.addProperty("properties.link_text", value=" | ".join(ref.link_texts))
                if ref.is_forwarded:
                    entity.addProperty("properties.forwarded", value="true")

                entity.setLinkThickness(2)
        except Exception as e:
            response.addUIMessage(f"Error finding bot referral links: {e}", messageType="PartialError")
