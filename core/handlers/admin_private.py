import json
import os
import uuid
from aiogram import Bot, Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import User, Card
from core.database import orm_query as orm
from core.filters import IsAdmin


from core.keyboards import get_callback_btns


admin_router = Router()
admin_router.message.filter(IsAdmin())

admin_main_kb = get_callback_btns(
    btns={
        "Карты": "edit_cards",
        "Уведомления": "edit_notifications",
        "Лимиты": "edit_limits",
        "Внешные ссылки": "external_links",
        "Статистика": "statistics",
    },
)

DAYS = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]


@admin_router.message(Command("admin"))
async def admin_features(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Что хотите сделать?", reply_markup=admin_main_kb)


@admin_router.callback_query(F.data == "admin")
async def callback_admin_features(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Что хотите сделать?", reply_markup=admin_main_kb)


@admin_router.callback_query(F.data == "edit_cards")
async def callback_edit_cards(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    all_cards = await orm.orm_read(session=session, model=Card)
    btns = {}
    text = "Карточки"

    if all_cards is False:
        await callback.message.answer("Виникла помилка 😞...")
        await admin_features(callback.message, state)
        return

    if all_cards:
        for card in all_cards:
            btns[
                f"{card.description[:40]}{'...' if card.description and len(card.description) > 30 else ''}"
            ] = f"card_{card.pk}"
    else:
        text = "Нет карточек"

    btns["Добавить карточку"] = "add_card"
    btns["Назад"] = "admin"

    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(
            text=text, reply_markup=get_callback_btns(btns=btns, sizes=(1,))
        )
    else:
        await callback.message.edit_text(
            text=text, reply_markup=get_callback_btns(btns=btns, sizes=(1,))
        )


async def edit_cards(message: Message, session: AsyncSession, text: str = None):
    all_cards = await orm.orm_read(session=session, model=Card)
    btns = {}

    if not text:
        text = "Карточки"

    if all_cards:
        for card in all_cards:
            btns[
                f"{card.description[:40]}{'...' if card.description and len(card.description) > 30 else ''}"
            ] = f"card_{card.pk}"
    else:
        text = "Нет карточек 😞"

    btns["Добавить карточку"] = "add_card"
    btns["Назад"] = "admin"

    await message.answer(
        text=text, reply_markup=get_callback_btns(btns=btns, sizes=(1,))
    )


@admin_router.callback_query(F.data.startswith("card_"))
async def callback_card(callback: CallbackQuery, session: AsyncSession):
    pk = int(callback.data.split("_")[1])
    card = await orm.orm_read(session=session, model=Card, pk=pk)
    photo = FSInputFile(card.image, filename="card.jpg")
    btns = get_callback_btns(
        btns={
            "Редактировать описание": f"edit_card_{card.pk}",
            "Удалить": f"delete_card_{card.pk}",
            "Назад": "edit_cards",
        },
        sizes=(1,),
    )

    await callback.message.delete()
    await callback.message.answer_photo(
        photo=photo, caption=card.description, reply_markup=btns
    )


class EditDesc(StatesGroup):
    description = State()


# EDIT CARD DESCRIPTION
@admin_router.callback_query(F.data.startswith("edit_card_"))
async def callback_edit_card(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    pk = int(callback.data.split("_")[2])
    card = await orm.orm_read(session=session, model=Card, pk=pk)

    await callback.answer()
    await callback.message.answer(text="Введите новое описание")
    await state.set_data({"card": card})
    await state.set_state(EditDesc.description)


# EDIT CARD STATE DESCRIPTION
@admin_router.message(EditDesc.description)
async def edit_card_description(
    message: Message, state: FSMContext, session: AsyncSession
):
    data = await state.get_data()
    card = data["card"]
    await orm.orm_update(
        session=session, model=Card, pk=card.pk, data={"description": message.text}
    )
    await message.answer("Описание изменено")
    await edit_cards(message, session=session)


# DELETE CARD
@admin_router.callback_query(F.data.startswith("delete_card_"))
async def callback_delete_card(callback: CallbackQuery, session: AsyncSession):
    pk = int(callback.data.split("_")[2])
    await orm.orm_delete(session=session, model=Card, pk=pk)
    result = await callback.message.delete()

    if result:
        await callback.answer("Карточка удалена")
        await edit_cards(callback.message, session=session)
    else:
        await callback.answer("Виникла помилка 😞...")


class AddCard(StatesGroup):
    description = State()
    image = State()


# ADD CARD
@admin_router.callback_query(F.data == "add_card")
async def callback_add_card(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Введите описание карточки")

    await state.set_state(AddCard.description)


# ADD CARD STATE DESCRIPTION
@admin_router.message(AddCard.description)
async def add_card_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Отправьте карточку")
    await state.set_state(AddCard.image)


# ADD CARD STATE IMAGE
@admin_router.message(AddCard.image, F.photo)
async def add_card_image(message: Message, state: FSMContext, session: AsyncSession):
    desc = await state.get_value("description")

    unique_filename = str(uuid.uuid4()) + ".jpg"
    file_path = os.path.join("images", unique_filename)

    await message.bot.download(file=message.photo[-1].file_id, destination=file_path)

    data = {
        "description": desc,
        "image": file_path,
    }

    await orm.orm_create(
        session,
        Card,
        data,
    )

    await state.clear()
    await edit_cards(message, session, text="Карточка добавлена")


@admin_router.callback_query(F.data == "external_links")
async def callback_external_links(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    btns = get_callback_btns(
        btns={
            "Купить карты": "buy_cards_link",
            "Дать полный расклад карт": "full_card_link",
            "Назад": "admin",
        },
        sizes=(1,),
    )

    await callback.message.edit_text(text="Изменить ссылку для...", reply_markup=btns)


class ChangeLink(StatesGroup):
    link_buy_cards = State()
    link_full_pack = State()


back_to_external_links = get_callback_btns(
    btns={
        "Назад": "external_links",
    },
    sizes=(1,),
)


@admin_router.callback_query(F.data == "buy_cards_link")
async def callback_buy_cards_link(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        text="Введите ссылку", reply_markup=back_to_external_links
    )
    await state.set_state(ChangeLink.link_buy_cards)


@admin_router.message(ChangeLink.link_buy_cards)
async def change_buy_cards_link(
    message: Message, state: FSMContext, session: AsyncSession
):
    url = message.text

    if not url.startswith("https://") and not url.startswith("http://"):
        await message.answer(
            "Введите корректную ссылку", reply_markup=back_to_external_links
        )
        await state.set_state(ChangeLink.link_buy_cards)
        return

    try:
        with open("config.json", "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        data = {}

    data["buy_cards_link"] = url

    with open("config.json", "w") as f:
        json.dump(data, f)

    await message.answer("Ссылка изменена")
    await admin_features(message, state)


@admin_router.callback_query(F.data == "full_card_link")
async def callback_full_card_link(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        text="Введите ссылку", reply_markup=back_to_external_links
    )
    await state.set_state(ChangeLink.link_full_pack)


@admin_router.message(ChangeLink.link_full_pack)
async def change_full_card_link(
    message: Message, state: FSMContext, session: AsyncSession
):
    url = message.text

    if not url.startswith("https://") and not url.startswith("http://"):
        await message.answer(
            "Введите корректную ссылку", reply_markup=back_to_external_links
        )
        await state.set_state(ChangeLink.link_full_pack)
        return

    try:
        with open("config.json", "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        data = {}

    data["full_card_link"] = url

    with open("config.json", "w") as f:
        json.dump(data, f)

    await message.answer("Ссылка изменена")
    await admin_features(message, state)


# NOTIFICATIONS
@admin_router.callback_query(F.data == "edit_notifications")
async def callback_edit_notifications(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    btns = get_callback_btns(
        btns={
            "Изменить время": "change_time",
            "Изменить дни": "change_days",
            "Назад": "admin",
        },
        sizes=(1,),
    )

    await callback.message.edit_text(text="Что хотите сделать?", reply_markup=btns)


# CHANGE TIME MENU
@admin_router.callback_query(F.data == "change_time")
async def callback_change_time(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    hour_btns = {
        "Назад": "edit_notifications",
    }

    for hour in range(6, 23):  # Від 6:00 до 22:00 (22 включно)
        hour_btns[f"{hour:02d}:00"] = f"change_time_{hour}"

    with open("config.json", "r") as f:
        data = json.load(f)

    hour = data.get("notification_time")

    if hour:
        await callback.message.edit_text(
            text=f"Выберите время. Текущее время: {hour:02d}:00",
            reply_markup=get_callback_btns(
                btns=hour_btns,
                sizes=(1, 3),
            ),
        )
    else:
        await callback.message.edit_text(
            text="Выберите время",
            reply_markup=get_callback_btns(
                btns=hour_btns,
                sizes=(
                    1,
                    3,
                ),
            ),
        )


# SELECT TIME
@admin_router.callback_query(F.data.startswith("change_time_"))
async def callback_change_time(callback: CallbackQuery, state: FSMContext):
    hour = int(callback.data.split("_")[2])

    with open("config.json", "r") as f:
        data = json.load(f)

    data["notification_time"] = hour

    with open("config.json", "w") as f:
        json.dump(data, f)

    await callback.answer("Время изменено")
    await callback_admin_features(callback, state)


# CHANGE DAYS MENU
@admin_router.callback_query(F.data == "change_days")
async def callback_change_days(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    with open("config.json", "r") as f:
        data = json.load(f)

    days = data.get("notification_days")
    days_btns = {"Назад": "edit_notifications"}

    for i, day in enumerate(DAYS):
        if str(i) in days:
            days_btns[f"{day} ✅"] = f"change_day_{i}"
        else:
            days_btns[day] = f"change_day_{i}"

    btns = get_callback_btns(
        btns=days_btns,
        sizes=(1, 2),
    )

    await callback.message.edit_text(text="Выберите дни", reply_markup=btns)


# SELECT DAY
@admin_router.callback_query(F.data.startswith("change_day_"))
async def callback_change_day_status(callback: CallbackQuery, state: FSMContext):
    day = callback.data.split("_")[2]

    with open("config.json", "r") as f:
        data = json.load(f)

    if data.get("notification_days") is None:
        data["notification_days"] = [day]
    elif day not in data["notification_days"]:
        data["notification_days"].append(day)
    else:
        data["notification_days"].remove(day)

    with open("config.json", "w") as f:
        json.dump(data, f)

    await callback.answer("День изменен")
    await callback_change_days(callback, state)
