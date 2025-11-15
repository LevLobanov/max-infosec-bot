from maxapi.types import MessageCreated
from maxapi.context import MemoryContext
import logging
from .utils import extract_message_text, get_chat_type
from .groups import handle_group_chat_message
from .privates import handle_private_chat_message

logger = logging.getLogger(__name__)


async def handle_text_message(event: MessageCreated, context: MemoryContext):
    text = extract_message_text(event.message)

    if not text:
        return

    chat_type = get_chat_type(event)
    user_data = await context.get_data()

    if chat_type == "private":
        await handle_private_chat_message(event, context, text, user_data)
    else:
        if user_data.get("is_collecting"):
            await handle_group_chat_message(event, context, text, user_data)
