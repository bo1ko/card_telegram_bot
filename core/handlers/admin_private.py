import os
import uuid
from aiogram import Bot, Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import User, UserCard, Card
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

    if callback.message.content_type == F.photo:
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
