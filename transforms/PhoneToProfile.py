"""
Transform: Phone to Telegram Profile
Resolves a phone number to a real Telegram user profile using MTProto contact import.
"""

from typing import Optional, Tuple
from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.types import InputPhoneContact, User

from extensions import registry
from client import run_telegram, get_client
from utils import safe_get_identifier, normalize_phone, download_avatar_b64, process_profile_entity


async def fetch_profile_by_phone(phone: str) -> Optional[Tuple[User, str]]:
    client = get_client()
    clean_phone = normalize_phone(phone)
    if not clean_phone:
        return None

    try:
        contacts = await client.import_contacts([InputPhoneContact(clean_phone, "TargetProfile")])
        if contacts and contacts.users:
            user = contacts.users[0]
            # Clean up the imported contact immediately
            try:
                await client.delete_contacts(user.id)
            except Exception:
                pass

            avatar_b64 = await download_avatar_b64(client, user)
            return user, avatar_b64
    except Exception:
        pass

    return None


@registry.register_transform(
    display_name="To Telegram Profile",
    input_entity="maltego.PhoneNumber",
    description="Resolves a phone number to a Telegram user profile via MTProto",
    output_entities=["interlinked.telegram.UserProfile"],
)
class PhoneToProfile(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        phone = safe_get_identifier(request, "phonenumber")
        if not phone:
            response.addUIMessage("No phone number specified", messageType="PartialError")
            return

        try:
            result = run_telegram(fetch_profile_by_phone(phone))
            if result:
                user, avatar_b64 = result
                entity = process_profile_entity(user, avatar_b64=avatar_b64)
                entity.addProperty("properties.phone", value=phone)
                entity.setLinkThickness(2)
                response.entities.append(entity)
            else:
                response.addUIMessage("No Telegram account found for this phone number", messageType="Inform")
        except Exception as e:
            response.addUIMessage(f"Error resolving phone number: {e}", messageType="PartialError")
