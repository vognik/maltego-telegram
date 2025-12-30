from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from settings import app, loop
from extensions import registry
from utils import process_profile_entity

from pyrogram import enums


async def fetch_group_adminsistrators(username: str):
    administrators = []

    async with app:
        async for m in app.get_chat_members(
            username, filter=enums.ChatMembersFilter.ADMINISTRATORS
        ):
            administrators.append(m)

    return [i.user for i in administrators]


@registry.register_transform(
    display_name="To Group Admins",
    input_entity="interlinked.telegram.Group",
    description="This Transform finds the administrators of the group",
    output_entities=["interlinked.telegram.UserProfile"],
)
class GroupToAdmins(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        username = request.getProperty("properties.username")
        administrators = loop.run_until_complete(fetch_group_adminsistrators(username))

        for admin in administrators:
            admin_entity = process_profile_entity(admin)

            admin_entity.setLinkThickness(2)
            response.entities.append(admin_entity)
