import logging

logger = logging.getLogger(__name__)


def extract_message_text(message):
    if hasattr(message, "body") and message.body:
        if hasattr(message.body, "text") and message.body.text:
            return message.body.text.strip()
        if hasattr(message.body, "caption") and message.body.caption:
            return message.body.caption.strip()

    if hasattr(message, "link") and message.link:
        if hasattr(message.link, "message") and message.link.message:
            if hasattr(message.link.message, "text") and message.link.message.text:
                return message.link.message.text.strip()
            if (
                hasattr(message.link.message, "caption")
                and message.link.message.caption
            ):
                return message.link.message.caption.strip()

    if hasattr(message, "text") and message.text:
        return message.text.strip()

    return ""


def get_sender_name(from_user):
    if hasattr(from_user, "first_name") and from_user.first_name:
        return from_user.first_name
    elif hasattr(from_user, "username") and from_user.username:
        return from_user.username
    return "Неизвестный"


def get_chat_type(event):
    if hasattr(event, "chat") and event.chat:
        if hasattr(event.chat, "type"):
            chat_type = str(event.chat.type)

            if "DIALOG" in chat_type:
                return "private"
            elif "CHAT" in chat_type:
                return "group"

    return "private"


def clean_command_text(text):
    if not text:
        return ""

    import re

    text = re.sub(r"@\w+\s*", "", text).strip()

    return text
