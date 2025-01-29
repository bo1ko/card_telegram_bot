from aiogram import F, types, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, or_f

from core.keyboards import get_callback_btns

user_router = Router()


@user_router.message(CommandStart())
async def start_cmd(message: types.Message):
    main_menu_btns = get_callback_btns(
        btns={
            "Карта дня 🔮": "card",
            "Купить карты 🛒": "buy",
            "Дать полный расклад карт 🃏": "full_pack",
            "Подписаться на ежедневную карту 📩": "subscribe",
        },
        sizes=(2, 1),
    )
    await message.answer("Главное меню", reply_markup=main_menu_btns)
