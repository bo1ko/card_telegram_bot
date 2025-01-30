from datetime import datetime, timedelta, timezone
import json
import random
from zoneinfo import ZoneInfo
from aiogram import F, types, Router
from sqlalchemy.ext.asyncio import AsyncSession

from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, Command, or_f

from core.keyboards import get_callback_btns, get_inlineMix_btns
from core.database.models import User, Card
from core.database import orm_query as orm
from core.utils import generate_main_menu

user_router = Router()


@user_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    main_menu_btns = await generate_main_menu(message.from_user.id, session)

    user = await orm.orm_read(session=session, model=User, tg_id=message.from_user.id)

    if not user:
        if message.from_user.username:
            await orm.orm_create(
                session,
                User,
                {"tg_id": message.from_user.id, "username": message.from_user.username},
            )
        else:
            await orm.orm_create(session, User, {"tg_id": message.from_user.id})

    await message.answer("Главное меню 👑", reply_markup=main_menu_btns)


@user_router.callback_query(F.data == "menu")
async def start_callback(
    callback: types.CallbackQuery, state: FSMContext, session: AsyncSession
):
    await state.clear()
    main_menu_btns = await generate_main_menu(callback.from_user.id, session=session)

    if callback.message.photo:
        await callback.answer()
        await callback.message.answer("Главное меню 👑", reply_markup=main_menu_btns)
    else:
        await callback.message.edit_text("Главное меню 👑", reply_markup=main_menu_btns)

@user_router.callback_query(F.data == "card")
async def callback_card(callback: types.CallbackQuery, session: AsyncSession):
    all_cards = await orm.orm_read(session=session, model=Card, as_iterable=True)
    user = await orm.orm_read(
        session=session, model=User, tg_id=callback.from_user.id, as_iterable=False
    )
    actual_time = datetime.now(timezone(timedelta(hours=2)))
    free_cards = []
    exiting_cards = user.cards or {}
    random_card = None

    kyiv_time_zone = ZoneInfo("Europe/Kiev")
    today_kyiv = datetime.now(kyiv_time_zone).date()

    today_elements = {
        key: value
        for key, value in exiting_cards.items()
        if datetime.fromisoformat(value).astimezone(kyiv_time_zone).date() == today_kyiv
    }

    if len(today_elements) > 3:
        await callback.answer("Хватит, иди работай!")
        return

    # if in db no cards
    if not all_cards:
        await callback.message.answer("Карт нету")
        return

    # if user has'nt cards
    if not exiting_cards:
        random_card = random.choice(all_cards)
    else:
        # if user has cards
        for card in all_cards:
            # if card is not in exiting cards
            if not str(card.pk) in exiting_cards.keys():
                free_cards.append(card)  # add to free_cards list
            else:
                # if card is in exiting cards, check the freshness of the card by date (10 days)
                exiting_time = datetime.fromisoformat(exiting_cards[str(card.pk)])

                if (actual_time - exiting_time) > timedelta(days=10):
                    free_cards.append(card)

    if free_cards:
        random_card = random.choice(free_cards)
        exiting_cards[random_card.pk] = actual_time.isoformat()
    elif random_card is not None:
        exiting_cards[random_card.pk] = actual_time.isoformat()
    else:
        await callback.answer()
        await callback.message.edit_text(
            "Карты закончились 😞",
            reply_markup=get_callback_btns(btns={"Назад ⏪": "menu"}),
        )
        return

    await orm.orm_update(
        session=session, model=User, pk=user.pk, data={"cards": exiting_cards}
    )

    photo = FSInputFile(random_card.image, filename="card.jpg")

    await callback.message.delete()
    await callback.message.answer_photo(
        photo=photo,
        caption=random_card.description,
        reply_markup=get_callback_btns(btns={"Назад ⏪": "menu"}),
    )


@user_router.callback_query(F.data == "subscribe")
async def callback_subscribe(
    callback: types.CallbackQuery, state: FSMContext, session: AsyncSession
):
    user = await orm.orm_read(
        session=session, model=User, tg_id=callback.from_user.id, as_iterable=False
    )

    await orm.orm_update(
        session=session,
        model=User,
        pk=user.pk,
        data={"subscription": True},
    )

    await callback.answer("Вы подписались на ежедневную карту ✅🎉")
    await start_callback(callback, state, session)


@user_router.callback_query(F.data == "unsubscribe")
async def callback_unsubscribe(
    callback: types.CallbackQuery, state: FSMContext, session: AsyncSession
):
    user = await orm.orm_read(
        session=session, model=User, tg_id=callback.from_user.id, as_iterable=False
    )

    await orm.orm_update(
        session=session,
        model=User,
        pk=user.pk,
        data={"subscription": False},
    )

    await callback.answer("Вы отписались от ежедневной карты ❌")
    await start_callback(callback, state, session)
