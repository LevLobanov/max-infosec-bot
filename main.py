import asyncio
from bot import bot_entry
from config import settings


async def main():
    await bot_entry(settings.MAX_BOT_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(bot_entry(settings.MAX_BOT_TOKEN))
    except KeyboardInterrupt:
        print("Stopped by Ctrl + C")
