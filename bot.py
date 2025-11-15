import asyncio
from datetime import datetime
import logging
import re
import textwrap
from typing import Any, Awaitable, Callable, Dict, Optional
from urllib.parse import urlparse
import aiohttp
from maxapi import Bot, Dispatcher, F
from maxapi.context import StatesGroup, State, MemoryContext
from maxapi.enums.parse_mode import ParseMode
from maxapi.enums.attachment import AttachmentType
from maxapi.enums.chat_type import ChatType
from maxapi.filters.middleware import BaseMiddleware
from maxapi.types import (
    Message,
    Command,
    BotStarted,
    MessageCreated,
    MessageCallback,
    Attachment,
    LinkButton,
    CallbackButton,
    ButtonsPayload,
    BotAdded,
    UpdateUnion,
)
from handlers.callbacks import handle_complete_conversation
from handlers.commands import handle_check
from handlers.groups import add_message_to_group_conversation
from handlers.privates import add_message_to_private_conversation
from leaks_aggregator import search_leaks, shutdown_all_clients
from services.ai_analyzer import init_ai_analyzer
from services.balance_checker import init_balance_checker
from virus_checker import check_link, check_file, exit_vt_client
from config import settings

dp = Dispatcher()


class IgnoreOldUpdatesMiddleware(BaseMiddleware):
    def __init__(self):
        self.start_time = datetime.now()

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: UpdateUnion,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, MessageCreated):
            msg = event.message
            event_time = datetime.fromtimestamp(msg.timestamp / 1000)

            if event_time < self.start_time:
                print(f"⏪ Игнор (старое сообщение): {msg.body.text!r}")
                return None

        if isinstance(event, MessageCallback):
            event_time = datetime.fromtimestamp(event.timestamp / 1000)

            if event_time < self.start_time:
                print(f"⏪ Игнор (старое нажатие кнопки)")
                return None

        return await handler(event, data)


class S(StatesGroup):
    wait_for_leaks_check_data = State()


def menu_kb() -> Attachment:
    return ButtonsPayload(
        buttons=[[
            CallbackButton(text="Агрегатор утечек", payload="leaks_aggregator")
        ],[
            CallbackButton(text="Анализ сообщения", payload="message_analysis")
        ]]
    ).pack()


@dp.bot_started()
async def bot_started(event: BotStarted):
    if event.bot:
        await event.bot.send_message(event.chat_id, text="Привет! /start")


@dp.message_created(Command("start"))
async def command_start(event: MessageCreated):
    await event.message.answer(
        textwrap.dedent(
            f"""\
            Привет, **{event.message.sender.first_name} {event.message.sender.last_name or ""}**!
            Это бот-помощник для цифровой гигиены. У него есть несколько функций:
                1) Чтобы проверить свои пароли, почты или номер телефона на наличие в утекших базах данных, нажми **Агрегатор утечек**.
                2) Чтобы проверить файлы или ссылки на вирусы - пришлите их мне в чат.
                3) Чтобы проверить сообщения на мошеннические мотивы, нажми **Проверка на мошенников**
            """
        ),
        parse_mode=ParseMode.MARKDOWN,
        attachments=[menu_kb()],
    )


@dp.bot_added()
async def bot_added_to_chat(event: BotAdded):
    if not event.is_channel and event.bot:
        await event.bot.send_message(
            chat_id=event.chat_id,
            text="""\
                Привет, я помощник по кибербезопасности!

                Спасибо, что добавили меня в чат. Вот, что я умею:
                **/start** - Стартовое сообщение
                **/help** | **/справка** - Вывести подсказки по командам
                """,
            parse_mode=ParseMode.MARKDOWN,
        )


@dp.message_created(Command(["help", "справка"]))
async def send_help_message(event: MessageCreated):
    await event.message.reply(
        text=textwrap.dedent(
            """\
            Вот мои команды:
            **/start** - Стартовое сообщение
            **/help** | **/справка** - Вывести подсказки по командам
            """
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


@dp.message_created(Command("check"))
async def check_command(event: MessageCreated, context: MemoryContext):
    await handle_check(event, context)


@dp.message_callback(F.callback.payload == "leaks_aggregator")
async def message_callback(event: MessageCallback, context: MemoryContext):
    await context.set_state(S.wait_for_leaks_check_data)
    await event.message.answer(
        "Пришлите свои данные для проверки на наличие утечек (Номер телефона / почту / пароли / логины)"
    )


@dp.message_callback(F.callback.payload == "message_analysis")
async def message_analysis(event: MessageCallback, context: MemoryContext):
    await handle_check(event, context)


@dp.message_callback(F.callback.payload == "complete")
@dp.message_callback(F.callback.payload == "cancel")
async def handle_conversation(event: MessageCallback, context: MemoryContext):
    await handle_complete_conversation(event, context)


def create_data_leak_check_kb() -> Attachment:
    return ButtonsPayload(
        buttons=[[CallbackButton(text="Проверить еще", payload="leaks_aggregator")]]
    ).pack()


@dp.message_created(F.message.body.text, S.wait_for_leaks_check_data)
async def check_data_for_leaks(event: MessageCreated, context: MemoryContext):
    await event.message.answer(text="Получил ваши данные, проверяю на утечки...")
    await context.clear()
    asyncio.create_task(check_leaks_and_send_result(event.message))


@dp.message_created(F.message.body.attachments[0].type == AttachmentType.FILE)
async def check_file_for_viruses(event: MessageCreated):
    if event.chat and event.chat.type == ChatType.DIALOG:
        if event.message.body.attachments:
            requested_file = event.message.body.attachments[0]
            if requested_file.type == AttachmentType.FILE:
                async with aiohttp.ClientSession() as session:
                    async with session.get(requested_file.payload.url) as resp:  # type: ignore
                        if not resp.ok:
                            await event.message.reply(
                                text="Не удалось получить файл, попробуйте еще раз"
                            )
                        temp_file_name = (
                            f"temp_file_{event.message.sender.user_id}"
                            + ("." + requested_file.filename.split(".")[-1])
                            if requested_file.filename
                            else ""
                        )
                        with open(temp_file_name, "wb") as temp_file:
                            async for chunk in resp.content.iter_chunked(1024):
                                temp_file.write(chunk)
                await event.message.reply("Получил ваш файл, проверяю на угрозы...")
                await scan_and_send_result(event.message, temp_file_name)
            else:
                await event.message.reply(text="Пожалуйста пришлите один файл")
        else:
            await event.message.reply(
                text="Пожалуйста пришлите файл. Если это изображение - выберите опцию отправить файлом"
            )


@dp.message_created(F.message.body.text)
async def check_link_for_viruses(event: MessageCreated, context: MemoryContext):
    if event.chat and event.chat.type == ChatType.DIALOG:
        user_data = await context.get_data()
        if user_data.get("is_collecting"):
            await add_message_to_private_conversation(event, context, event.message.body.text)
            return
        if is_online_link(event.message.body.text):
            await event.message.reply(text="Получил вашу ссылку, проверяю на угрозы...")
            asyncio.create_task(scan_and_send_result(event.message))
        else:
            await event.message.reply(text="Не могу распознать ссылку")
    elif event.chat and event.chat.type == ChatType.CHAT:
        user_data = await context.get_data()
        if user_data.get("is_collecting"):
            session_owner = user_data.get("session_owner")
            if event.from_user and session_owner == event.from_user.user_id:
                await add_message_to_group_conversation(event, context, event.message.body.text)
            return


def create_scan_result_kb(scan_id: str | None = None) -> Attachment:
    return ButtonsPayload(
        buttons=[
            [
                (
                    LinkButton(
                        text="Полный отчет",
                        url=f"https://www.virustotal.com/gui/file-analysis/{scan_id}",
                    )
                    if scan_id
                    else LinkButton(
                        text="Проверить на угрозы", url="https://www.virustotal.com"
                    )
                )
            ]
        ]
    ).pack()


async def scan_and_send_result(message: Message, filepath: str | None = None) -> None:
    if filepath:
        id, result = await check_file(filepath)
    else:
        id, result = await check_link(message.body.text)
    if result:
        await message.reply(
            text=textwrap.dedent(
                f"""\
                Результаты сканирования:
                ❌ Вредоносный: {result.get("malicious", "Нет данных")}
                ⚠ Подозрительный: {result.get("suspicious", "Нет данных")}
                ✅ Безопасный: {result.get("harmless", "Нет данных")}
                ❔ Не оценено: {result.get("undetected", "Нет данных")}

                Чтобы прочитать полный отчет и посмотреть отзывы нажмите на кнопку ниже👇
                """
            ),
            attachments=[create_scan_result_kb(id)],
        )
    else:
        await message.reply(
            text="Не получилось обработать ссылку или файл. Пожалуйста, попробуйте чуть позже или проверьте ее сами на Virustotal.com нажав на кнопку ниже👇",
            attachments=[create_scan_result_kb()],
        )


async def check_leaks_and_send_result(message: Message) -> None:
    result = await search_leaks(message.body.text)
    if result:
        await message.reply(
            text=textwrap.dedent(
                f"""\
            ❗ ^^Найдено {len(result)} утечек^^:
            {
                "\n".join(map(lambda leak: f"Сервис: {leak.site or "Неизвестно"} Дата: {leak.breach_date or "Неизвестно"}", result))
            }
            """
            ),
            parse_mode=ParseMode.MARKDOWN,
            attachments=[create_data_leak_check_kb()],
        )
    else:
        await message.reply(
            "Утечек не найдено", attachments=[create_data_leak_check_kb()]
        )


def is_online_link(url_string: str) -> Optional[str]:
    """
    Проверяет, является ли строка валидной ссылкой (с протоколом или без).
    Возвращает URL с https://, если всё корректно.
    """
    if "://" not in url_string:
        candidate = "https://" + url_string
    else:
        candidate = url_string

    try:
        result = urlparse(candidate)

        # Извлекаем домен
        hostname = result.hostname

        is_valid = (
            hostname is not None and re.match(r"^[a-zA-Z0-9.-]+$", hostname) is not None
        )

        if is_valid:
            return candidate
        return None
    except Exception:
        return None


async def bot_entry(max_bot_token: str):
    bot = Bot(max_bot_token)
    dp.middleware(IgnoreOldUpdatesMiddleware())
    bot_task = asyncio.create_task(dp.start_polling(bot))

    try:
        init_ai_analyzer(settings.AI_TUNNEL_TOKEN)
        init_balance_checker(settings.AI_TUNNEL_TOKEN)
        logging.info("AI анализатор и баланс-чекер инициализированы")
    except Exception as e:
        logging.error(f"Ошибка инициализации AI: {e}")
    try:
        return await bot_task
    except asyncio.CancelledError:
        bot_task.cancel()
        try:
            await bot_task
        except:
            pass
    finally:
        await bot.close_session()
        await shutdown_all_clients()
        await exit_vt_client()
