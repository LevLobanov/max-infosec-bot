from maxapi.types import MessageCreated, CallbackButton, ButtonsPayload
from maxapi.context import MemoryContext
import logging
from datetime import datetime
from .utils import get_sender_name, extract_message_text

logger = logging.getLogger(__name__)


async def start_group_check_session(event: MessageCreated, context: MemoryContext):
    user_data = await context.get_data()

    if (
        user_data.get("is_collecting")
        and user_data.get("session_owner") == event.from_user.user_id
    ):
        await add_message_to_group_conversation(
            event, context, extract_message_text_from_object(event.message.link.message)
        )
        return

    message_to_analyze = event.message.link.message
    text = extract_message_text_from_object(message_to_analyze)

    if not text:
        await event.message.answer(
            "❌ Не удалось извлечь текст из сообщения для анализа"
        )
        return

    sender_info = get_sender_info(message_to_analyze)

    await context.update_data(
        is_collecting=True,
        session_owner=event.from_user.user_id,
        messages=[
            {
                "text": text,
                "sender_id": get_sender_id(message_to_analyze),
                "sender_name": sender_info,
                "timestamp": datetime.now().isoformat(),
            }
        ],
        chat_type="group",
    )

    buttons = [
        [
            CallbackButton(text="✅ Проанализировать диалог", payload="complete"),
            CallbackButton(text="❌ Отмена", payload="cancel"),
        ]
    ]

    buttons_payload = ButtonsPayload(buttons=buttons).pack()

    await event.message.answer(
        f"✅ Сообщение #1 сохранено\n\n"
        "Продолжайте присылать сообщения или нажмите кнопку для анализа.",
        attachments=[buttons_payload],
    )


async def handle_group_chat_message(
    event: MessageCreated, context: MemoryContext, text: str, user_data: dict
):
    if not user_data.get("is_collecting"):
        return

    session_owner = user_data.get("session_owner")
    if session_owner != event.from_user.user_id:
        return

    await add_message_to_group_conversation(event, context, text)


async def add_message_to_group_conversation(
    event: MessageCreated, context: MemoryContext, text: str
):
    user_data = await context.get_data()
    messages = user_data.get("messages", [])

    messages.append(
        {
            "text": text,
            "sender_id": event.from_user.user_id,
            "sender_name": get_sender_name(event.from_user),
            "timestamp": datetime.now().isoformat(),
        }
    )

    await context.update_data(messages=messages)

    message_count = len(messages)

    buttons = [
        [
            CallbackButton(text="✅ Проанализировать", payload="complete"),
            CallbackButton(text="❌ Отмена", payload="cancel"),
        ]
    ]

    buttons_payload = ButtonsPayload(buttons=buttons).pack()

    await event.message.answer(
        f"✅ Сообщение #{message_count} сохранено\n\n"
        "Продолжайте присылать сообщения или нажмите кнопку для анализа.",
        attachments=[buttons_payload],
    )


def extract_message_text_from_object(message_obj):
    if hasattr(message_obj, "text") and message_obj.text:
        return message_obj.text.strip()

    if hasattr(message_obj, "body") and message_obj.body:
        if hasattr(message_obj.body, "text") and message_obj.body.text:
            return message_obj.body.text.strip()
        if hasattr(message_obj.body, "caption") and message_obj.body.caption:
            return message_obj.body.caption.strip()

    return ""


def get_sender_info(message):
    if hasattr(message, "from_user") and message.from_user:
        return get_sender_name(message.from_user)

    if hasattr(message, "sender") and message.sender:
        return get_sender_name(message.sender)

    return "Неизвестный отправитель"


def get_sender_id(message):
    if hasattr(message, "from_user") and message.from_user:
        return message.from_user.user_id

    if hasattr(message, "sender") and message.sender:
        return message.sender.user_id

    return 0
