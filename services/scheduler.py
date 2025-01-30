from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot

from core.database.models import User
from core.database import orm_query as orm


async def send_daily_cards(bot: Bot, session: AsyncSession):
    users = await orm.orm_read(session=session, model=User, as_iterable=True)

    print(users)
    # await bot.send_photo(
    #     chat_id=user.telegram_id,
    #     photo=card.image,
    #     caption=f"📅 Ежедневная карта:\n{card.description}",
    # )
