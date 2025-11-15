from maxapi.types import MessageCreated, CallbackButton, ButtonsPayload
from maxapi.context import MemoryContext
import logging
from datetime import datetime
from .utils import extract_message_text, get_sender_name

logger = logging.getLogger(__name__)


async def handle_private_chat_message(
    event: MessageCreated, context: MemoryContext, text: str, user_data: dict
):
    if not user_data.get("is_collecting"):
        return

    await add_message_to_private_conversation(event, context, text)


async def add_message_to_private_conversation(
    event: MessageCreated, context: MemoryContext, text: str
):
    user_data = await context.get_data()
    messages = user_data.get("messages", [])

    full_text = extract_full_message_text(event.message, text)

    messages.append(
        {
            "text": full_text,
            "sender_id": event.from_user.user_id,
            "sender_name": get_sender_name(event.from_user),
            "timestamp": datetime.now().isoformat(),
            "message_type": get_message_type(event.message),
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


def extract_full_message_text(message, base_text: str) -> str:
    text_parts = [base_text]

    if hasattr(message, "forward_from") and message.forward_from:
        forward_text = extract_forwarded_message_text(message)
        if forward_text:
            text_parts.append(f"[Переслано]: {forward_text}")

    if hasattr(message, "reply_to") and message.reply_to:
        reply_text = extract_reply_message_text(message.reply_to)
        if reply_text:
            text_parts.append(f"[Ответ на]: {reply_text}")

    return "\n".join(text_parts)


def extract_forwarded_message_text(message) -> str:
    if hasattr(message, "forward_from") and message.forward_from:
        if hasattr(message, "text") and message.text:
            return message.text
        if hasattr(message, "body") and message.body:
            if hasattr(message.body, "text") and message.body.text:
                return message.body.text
            if hasattr(message.body, "caption") and message.body.caption:
                return message.body.caption
    return ""


def extract_reply_message_text(reply_message) -> str:
    if hasattr(reply_message, "text") and reply_message.text:
        return reply_message.text

    if hasattr(reply_message, "body") and reply_message.body:
        if hasattr(reply_message.body, "text") and reply_message.body.text:
            return reply_message.body.text
        if hasattr(reply_message.body, "caption") and reply_message.body.caption:
            return reply_message.body.caption

    return ""


def get_message_type(message) -> str:
    if hasattr(message, "forward_from") and message.forward_from:
        return "forwarded"
    elif hasattr(message, "reply_to") and message.reply_to:
        return "reply"
    else:
        return "text"
