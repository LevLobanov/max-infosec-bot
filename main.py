import asyncio
import logging
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, Command, MessageCallback, BotCommand
from maxapi.context import MemoryContext
from maxapi.filters import F

from config import get_bot_token, get_ai_tunnel_key
from handlers.commands import handle_start, handle_help, handle_check
from handlers.messages import handle_text_message
from handlers.callbacks import handle_complete_conversation, handle_cancel_conversation

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def handle_callback(event: MessageCallback, context: MemoryContext):
    payload = event.callback.payload

    if payload == "complete":
        await handle_complete_conversation(event, context)
    elif payload == "cancel":
        await handle_cancel_conversation(event, context)


async def setup_bot_commands(bot: Bot):
    commands = [
        BotCommand(name="start", description="Запуск бота и описание"),
        BotCommand(name="help", description="Помощь и справка"),
        BotCommand(
            name="check", description="Анализ сообщения (ответьте на сообщение)"
        ),
    ]

    try:
        await bot.set_my_commands(*commands)
        logger.info("Команды бота успешно установлены")
    except Exception as e:
        logger.error(f"Ошибка установки команд бота: {e}")


async def main():
    token = get_bot_token()

    if not token:
        logger.error("Токен MAX бота не найден!")
        return

    logger.info("Запуск AntiScam бота...")

    api_key = get_ai_tunnel_key()
    if api_key:
        from services.ai_analyzer import init_ai_analyzer
        from services.balance_checker import init_balance_checker

        try:
            init_ai_analyzer(api_key)
            init_balance_checker(api_key)
            logger.info("AI анализатор и баланс-чекер инициализированы")
        except Exception as e:
            logger.error(f"Ошибка инициализации AI: {e}")

    try:
        bot = Bot(token)
        dp = Dispatcher()

        await setup_bot_commands(bot)

        dp.message_created(Command("start"))(handle_start)
        dp.message_created(Command("help"))(handle_help)
        dp.message_created(Command("check"))(handle_check)

        dp.message_created()(handle_text_message)
        dp.message_callback()(handle_callback)

        logger.info("Бот запущен!")

        await dp.start_polling(bot)

    except Exception as error:
        logger.error(f"Ошибка: {error}")


if __name__ == "__main__":
    asyncio.run(main())
