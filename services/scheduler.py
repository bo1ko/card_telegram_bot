from sqlalchemy.ext.asyncio import AsyncSession
import random
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram.types import Message, FSInputFile
from core.database.models import User, Card
from core.database import orm_query as orm

logger = logging.getLogger(__name__)


async def get_random_card(message: Message, session: AsyncSession) -> None:
    try:
        users = await orm.orm_read(session=session, model=User, as_iterable=True)
        logger.info(f"Fetched {len(users)} users for random card selection.")

        for user in users:
            if not user.subscription:
                continue

            # Get all cards from db
            all_cards = await orm.orm_read(
                session=session, model=Card, as_iterable=True
            )
            logger.info(
                f"User {user.pk}: Retrieved {len(all_cards)} cards from database."
            )

            actual_time = datetime.now(ZoneInfo("Europe/Kiev"))
            # Convert to offset-naive datetime
            actual_time_naive = actual_time.replace(tzinfo=None)
            free_cards = []
            exiting_cards = user.cards or {}

            # Get free cards
            for card in all_cards:
                if not str(card.pk) in exiting_cards.keys():
                    free_cards.append(card)
                else:
                    exiting_time = datetime.fromisoformat(exiting_cards[str(card.pk)])
                    if (actual_time - exiting_time) > timedelta(days=10):
                        free_cards.append(card)

            if free_cards:
                random.shuffle(free_cards)
                random_card = random.choice(free_cards)
                exiting_cards[random_card.pk] = actual_time.isoformat()
                await orm.orm_update(
                    session=session,
                    model=User,
                    pk=user.pk,
                    data={"cards": exiting_cards, "last_request": actual_time_naive},
                )
                logger.info(f"User {user.pk}: Assigned card {random_card.pk}.")
                logger.info(
                    f"User {user.pk}: Updated last_request to {actual_time.isoformat()}."
                )

                photo = FSInputFile(random_card.image, filename="card.jpg")

                await message.answer_photo(photo=photo)
                await message.answer(
                    text=f"Ежедневная карта 🃏\n\n{random_card.description}",
                )
                return
            logger.warning(f"User {user.pk}: No free cards available.")
            await message.answer(
                "Карты закончились 😞. Ежедневная карта будет доступна через 24 часа 🕛"
            )
    except Exception as e:
        logger.error(f"Error in get_random_card: {str(e)}")
        await message.answer("Произошла ошибка при получении карты 😞.")
