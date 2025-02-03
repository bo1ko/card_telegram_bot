from aiogram.types import BotCommand, BotCommandScopeChat
from aiogram import Bot

private = [
    BotCommand(command="admin", description="Адмін панель"),
]


async def set_admin_commands(admin_list: list, bot: Bot):
    for admin in admin_list:
        await bot.set_my_commands(private, scope=BotCommandScopeChat(admin))
