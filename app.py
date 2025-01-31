import asyncio
import logging
import json
import os

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommandScopeAllPrivateChats
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from dotenv import find_dotenv, load_dotenv

from core.middlewares import DataBaseSession
from core.database.engine import create_db, drop_db, session_maker
from core.handlers.user_private import user_router
from core.handlers.admin_private import admin_router
from core.common.admin_cmds_list import set_admin_commands
from core.common.user_cmds_list import private as user_cmds


load_dotenv(find_dotenv())

# Create directories if they don't exist
os.makedirs("images", exist_ok=True)
os.makedirs("logs", exist_ok=True)

# Create config.json if it doesn't exist
if not os.path.exists("config.json"):
    with open("config.json", "w") as f:
        json.dump(
            {
                "buy_cards_link": "https://www.google.com/",
                "full_card_link": "https://www.google.com/",
                "notification_time": 0,
                "notification_days": ["0"],
                "cards_limit": 3,
                "scheduler_status": False,
                "help_text": "Empty. Заполните вручную",
                "start_text": "Empty. Заполните вручную",
            },
            f,
        )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=os.getenv("TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

admin_list = os.getenv("ADMIN_LIST").replace(" ", "").split(",")
bot.my_admins_list = admin_list

dp = Dispatcher()
dp.include_router(user_router)
dp.include_router(admin_router)


async def on_startup(bot):
    # await drop_db()
    await create_db()


async def on_shutdown(bot):
    logger.info("Bot down")

    with open("config.json", "r") as f:
        data = json.load(f)

    if data.get("scheduler_status", True):
        data["scheduler_status"] = False

        with open("config.json", "w") as f:
            json.dump(data, f)

        logger.info("Scheduler status set to False in config.json")
    else:
        logger.info("Scheduler was already set to False in config.json")


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.update.middleware(DataBaseSession(session_pool=session_maker))

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands(
        commands=user_cmds, scope=BotCommandScopeAllPrivateChats()
    )
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.error("Bot stopped!")
