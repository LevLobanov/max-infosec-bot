from maxapi.types import MessageCallback
from maxapi.context import MemoryContext
from services.ai_analyzer import analyze_message_safe, AnalysisResult
import logging

logger = logging.getLogger(__name__)


async def handle_complete_conversation(event: MessageCallback, context: MemoryContext):
    user_data = await context.get_data()
    messages = user_data.get("messages", [])

    if not messages:
        await event.message.answer("❌ Нет сообщений для анализа")
        return

    chat_type = user_data.get("chat_type", "private")
    conversation_text = format_conversation_text(messages, chat_type)
    message_count = len(messages)

    analyzing_msg = await event.message.answer(
        f"🔍 Анализирую {message_count} сообщений..."
    )

    try:
        analysis_result = await analyze_message_safe(conversation_text)
        response = format_analysis_response(
            analysis_result, message_count, chat_type, messages
        )
        await event.message.answer(response)

    except Exception as e:
        logger.error(f"Ошибка при анализе диалога: {e}")
        await event.message.answer("❌ Произошла ошибка при анализе. Попробуйте позже.")
    finally:
        await context.clear()
        try:
            await analyzing_msg.delete()
        except:
            pass


async def handle_cancel_conversation(event: MessageCallback, context: MemoryContext):
    user_data = await context.get_data()
    message_count = len(user_data.get("messages", []))
    await context.clear()

    await event.message.answer(
        f"❌ Сбор сообщений отменен. Удалено {message_count} сообщений."
    )


def format_conversation_text(messages: list, chat_type: str) -> str:
    if not messages:
        return ""

    conversation = []
    speaker_mapping = {}
    speaker_count = 1

    for msg in messages:
        sender_id = msg["sender_id"]

        if sender_id not in speaker_mapping:
            speaker_mapping[sender_id] = f"Собеседник {speaker_count}"
            speaker_count += 1

        speaker_label = speaker_mapping[sender_id]
        conversation.append(f"{speaker_label}: {msg['text']}")

    if chat_type == "group":
        conversation.append(
            f"\n[Контекст: {len(messages)} сообщений из группового чата]"
        )
    else:
        conversation.append(f"\n[Контекст: {len(messages)} сообщений из личного чата]")

    return "\n".join(conversation)


def format_analysis_response(
    result: AnalysisResult, message_count: int, chat_type: str, messages: list
) -> str:
    if result.risk_score >= 90:
        risk_emoji = "🚫"
        risk_level = "ОЧЕНЬ ВЫСОКИЙ"
    elif result.risk_score >= 70:
        risk_emoji = "🔴"
        risk_level = "ВЫСОКИЙ"
    elif result.risk_score >= 50:
        risk_emoji = "🟠"
        risk_level = "ПОВЫШЕННЫЙ"
    elif result.risk_score >= 30:
        risk_emoji = "🟡"
        risk_level = "СРЕДНИЙ"
    else:
        risk_emoji = "🟢"
        risk_level = "НИЗКИЙ"

    indicators_text = (
        "\n".join([f"• {indicator}" for indicator in result.scam_indicators])
        if result.scam_indicators
        else "• Признаки не обнаружены"
    )

    if chat_type == "group" and message_count == 1:
        first_message = messages[0]
        display_text = (
            first_message["text"][:200] + "..."
            if len(first_message["text"]) > 200
            else first_message["text"]
        )
        return f"""{risk_emoji} АНАЛИЗ СООБЩЕНИЯ от {first_message['sender_name']}

📝 Текст: "{display_text}"

📊 Уровень риска: {result.risk_score}% ({risk_level})

🔍 Обнаруженные признаки:
{indicators_text}

💬 Анализ:
{result.analysis}

⚠️ Это автоматический анализ. Всегда проверяйте информацию!"""
    else:
        chat_type_text = "ГРУППОВОГО ЧАТА" if chat_type == "group" else "ДИАЛОГА"
        return f"""{risk_emoji} РЕЗУЛЬТАТ АНАЛИЗА {chat_type_text} ({message_count} сообщений)

Уровень риска: {result.risk_score}% ({risk_level})

Обнаруженные признаки:
{indicators_text}

Анализ:
{result.analysis}

⚠️ Это автоматический анализ. Всегда проверяйте информацию!"""
