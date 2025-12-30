from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import (
    MaltegoMsg,
    MaltegoTransform,
)
from settings import app, loop
from extensions import registry

from pyrogram.types import InputPhoneContact

from utils import process_profile_entity


async def fetch_profile_by_phone(phone: str):
    async with app:
        contacts = await app.import_contacts([InputPhoneContact(phone, "Foo")])
        if contacts.users:
            await app.delete_contacts(contacts.users[0].id)
            return await app.get_users(contacts.users[0].id)

    return


@registry.register_transform(
    display_name="To Telegram Profile",
    input_entity="maltego.PhoneNumber",
    description="Finds a user's Telegram profile by phone number",
    output_entities=["interlinked.telegram.UserProfile"],
)
class PhoneToProfile(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        phone = request.getProperty("phonenumber")
        profile = loop.run_until_complete(fetch_profile_by_phone(phone))

        if profile:
            entity = process_profile_entity(profile)

            entity.addProperty("properties.phone", value=phone)

            entity.setLinkThickness(2)
            response.entities.append(entity)
