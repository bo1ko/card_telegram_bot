import traceback
import logging
import uuid
import json
import os

from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.database.models import User, Card
from core.database import orm_query as orm
from core.filters import IsAdmin
from core.keyboards import get_callback_btns
from services.scheduler import get_random_card

logger = logging.getLogger(__name__)


admin_router = Router()
admin_router.message.filter(IsAdmin())

admin_main_kb = get_callback_btns(
    btns={
        "Карты": "edit_cards",
        "Уведомления": "edit_notifications",
        "Лимиты": "edit_limits",
        "Внешние ссылки": "external_links",
        "/help": "edit_help",
        "/start": "edit_start",
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

scheduler = AsyncIOScheduler()


@admin_router.message(Command("admin"))
async def admin_features(message: Message, state: FSMContext):
    try:
        await state.clear()
        await message.answer("Что хотите сделать?", reply_markup=admin_main_kb)
    except Exception:
        logger.error("Error in admin_features")
        logger.error(traceback.format_exc())
        await message.answer("Произошла ошибка 😞...")


@admin_router.callback_query(F.data == "admin")
async def callback_admin_features(callback: CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await callback.message.edit_text(
            "Что хотите сделать?", reply_markup=admin_main_kb
        )
    except Exception:
        logger.error("Error in callback_admin_features")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


@admin_router.callback_query(F.data == "edit_cards")
async def callback_edit_cards(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    try:
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
    except Exception:
        logger.error("Error in callback_edit_cards")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


async def edit_cards(message: Message, session: AsyncSession, text: str = None):
    try:
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
    except Exception:
        logger.error("Error in edit_cards")
        logger.error(traceback.format_exc())
        await message.answer("Произошла ошибка 😞...")


@admin_router.callback_query(F.data.startswith("card_"))
async def callback_card(callback: CallbackQuery, session: AsyncSession):
    try:
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
    except Exception:
        logger.error("Error in callback_card")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


class EditDesc(StatesGroup):
    description = State()


# EDIT CARD DESCRIPTION
@admin_router.callback_query(F.data.startswith("edit_card_"))
async def callback_edit_card(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    try:
        pk = int(callback.data.split("_")[2])
        card = await orm.orm_read(session=session, model=Card, pk=pk)

        await callback.answer()
        await callback.message.answer(text="Введите новое описание")
        await state.set_data({"card": card})
        await state.set_state(EditDesc.description)
    except Exception:
        logger.error("Error in callback_edit_card")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


# EDIT CARD STATE DESCRIPTION
@admin_router.message(EditDesc.description)
async def edit_card_description(
    message: Message, state: FSMContext, session: AsyncSession
):
    try:
        data = await state.get_data()
        card = data["card"]
        await orm.orm_update(
            session=session, model=Card, pk=card.pk, data={"description": message.text}
        )
        await message.answer("Описание изменено")
        await edit_cards(message, session=session)
    except Exception:
        logger.error("Error in edit_card_description")
        logger.error(traceback.format_exc())
        await message.answer("Произошла ошибка 😞...")


# DELETE CARD
@admin_router.callback_query(F.data.startswith("delete_card_"))
async def callback_delete_card(callback: CallbackQuery, session: AsyncSession):
    try:
        pk = int(callback.data.split("_")[2])
        await orm.orm_delete(session=session, model=Card, pk=pk)
        result = await callback.message.delete()

        if result:
            await callback.answer("Карточка удалена")
            await edit_cards(callback.message, session=session)
        else:
            await callback.answer("Виникла помилка 😞...")
    except Exception:
        logger.error("Error in callback_delete_card")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


class AddCard(StatesGroup):
    description = State()
    image = State()


# ADD CARD
@admin_router.callback_query(F.data == "add_card")
async def callback_add_card(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_text(text="Введите описание карточки")
        await state.set_state(AddCard.description)
    except Exception:
        logger.error("Error in callback_add_card")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


# ADD CARD STATE DESCRIPTION
@admin_router.message(AddCard.description)
async def add_card_description(message: Message, state: FSMContext):
    try:
        await state.update_data(description=message.text)
        await message.answer("Отправьте карточку")
        await state.set_state(AddCard.image)
    except Exception:
        logger.error("Error in add_card_description")
        logger.error(traceback.format_exc())
        await message.answer("Произошла ошибка 😞...")


# ADD CARD STATE IMAGE
@admin_router.message(AddCard.image, F.photo)
async def add_card_image(message: Message, state: FSMContext, session: AsyncSession):
    try:
        desc = await state.get_value("description")

        unique_filename = str(uuid.uuid4()) + ".jpg"
        file_path = os.path.join("images", unique_filename)

        await message.bot.download(
            file=message.photo[-1].file_id, destination=file_path
        )

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
    except Exception:
        logger.error("Error in add_card_image")
        logger.error(traceback.format_exc())
        await message.answer("Произошла ошибка 😞...")


@admin_router.callback_query(F.data == "external_links")
async def callback_external_links(callback: CallbackQuery, state: FSMContext):
    try:
        await state.clear()

        btns = get_callback_btns(
            btns={
                "Купить карты": "buy_cards_link",
                "Дать полный расклад карт": "full_card_link",
                "Назад": "admin",
            },
            sizes=(1,),
        )

        await callback.message.edit_text(
            text="Изменить ссылку для...", reply_markup=btns
        )
    except Exception:
        logger.error("Error in callback_external_links")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


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
    try:
        await callback.message.edit_text(
            text="Введите ссылку", reply_markup=back_to_external_links
        )
        await state.set_state(ChangeLink.link_buy_cards)
    except Exception:
        logger.error("Error in callback_buy_cards_link")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


@admin_router.message(ChangeLink.link_buy_cards)
async def change_buy_cards_link(
    message: Message, state: FSMContext, session: AsyncSession
):
    try:
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
    except Exception:
        logger.error("Error in change_buy_cards_link")
        logger.error(traceback.format_exc())
        await message.answer("Произошла ошибка 😞...")


@admin_router.callback_query(F.data == "full_card_link")
async def callback_full_card_link(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_text(
            text="Введите ссылку", reply_markup=back_to_external_links
        )
        await state.set_state(ChangeLink.link_full_pack)
    except Exception:
        logger.error("Error in callback_full_card_link")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


@admin_router.message(ChangeLink.link_full_pack)
async def change_full_card_link(
    message: Message, state: FSMContext, session: AsyncSession
):
    try:
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
    except Exception:
        logger.error("Error in change_full_card_link")
        logger.error(traceback.format_exc())
        await message.answer("Произошла ошибка 😞...")


# NOTIFICATIONS
@admin_router.callback_query(F.data == "edit_notifications")
async def callback_edit_notifications(callback: CallbackQuery, state: FSMContext):
    try:
        await state.clear()

        btns = get_callback_btns(
            btns={
                "Изменить время": "change_time",
                "Изменить дни": "change_days",
                "Статус рассылки": "status_scheduler",
                "Назад": "admin",
            },
            sizes=(1,),
        )

        await callback.message.edit_text(text="Что хотите сделать?", reply_markup=btns)
    except Exception:
        logger.error("Error in callback_edit_notifications")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


# STATUS SCHEDULER
@admin_router.callback_query(F.data == "status_scheduler")
async def callback_status_scheduler(callback: CallbackQuery):
    try:
        with open("config.json", "r") as f:
            data = json.load(f)

        status = data.get("scheduler_status", False)

        if status:
            btns = {
                "Выключить": "disable_scheduler",
                "Назад": "edit_notifications",
            }
        else:
            btns = {
                "Включить": "enable_scheduler",
                "Назад": "edit_notifications",
            }

        scheduler_btns = get_callback_btns(
            btns=btns,
            sizes=(1,),
        )

        await callback.message.edit_text(
            text=f"Статус рассылки: {'✅' if status else '❌'}",
            reply_markup=scheduler_btns,
        )
    except Exception:
        logger.error("Error in callback_status_scheduler")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


@admin_router.callback_query(F.data == "enable_scheduler")
async def callback_enable_scheduler(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    try:
        logger.info("Enabling scheduler...")

        if scheduler.running:
            scheduler.remove_all_jobs()
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped before enabling.")

        # Load configuration from config.json
        with open("config.json", "r") as f:
            config = json.load(f)
        logger.info("Configuration loaded successfully.")

        # Get notification time and days from config
        notification_time = config.get(
            "notification_time", 20
        )  # Default to 20 if not set
        notification_days = config.get(
            "notification_days", ["0"]
        )  # Default to ["0", "1"] if not set
        logger.info(
            f"Notification time set to {notification_time}, days: {notification_days}"
        )

        # Schedule the job using the loaded configuration
        scheduler.add_job(
            get_random_card,
            "cron",
            hour=notification_time,
            day_of_week=",".join(notification_days),
            args=[callback.message, session],
        )
        scheduler.start()

        with open("config.json", "r") as f:
            data = json.load(f)

        data["scheduler_status"] = True

        with open("config.json", "w") as f:
            json.dump(data, f)

        logger.info("Scheduler started successfully.")
        await callback.answer("Планировщик включен.")
        await callback_status_scheduler(callback)
    except Exception:
        logger.error("Error in callback_enable_scheduler")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


@admin_router.callback_query(F.data == "disable_scheduler")
async def callback_disable_scheduler(callback: CallbackQuery, state: FSMContext):
    try:
        logger.info("Disabling scheduler...")

        if scheduler.running:
            scheduler.remove_all_jobs()
            scheduler.shutdown(wait=False)
            logger.info("Scheduler disabled successfully.")
        else:
            logger.info("Scheduler was not running.")

        with open("config.json", "r") as f:
            data = json.load(f)

        data["scheduler_status"] = False

        with open("config.json", "w") as f:
            json.dump(data, f)

        await callback.answer("Планировщик выключен.")
        await callback_status_scheduler(callback)
    except Exception:
        logger.error("Error in callback_disable_scheduler")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


# CHANGE TIME MENU
@admin_router.callback_query(F.data == "change_time")
async def callback_change_time(callback: CallbackQuery, state: FSMContext):
    try:
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
    except Exception:
        logger.error("Error in callback_change_time")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


# SELECT TIME
@admin_router.callback_query(F.data.startswith("change_time_"))
async def callback_change_time(callback: CallbackQuery, state: FSMContext):
    try:
        hour = int(callback.data.split("_")[2])

        with open("config.json", "r") as f:
            data = json.load(f)

        data["notification_time"] = hour

        with open("config.json", "w") as f:
            json.dump(data, f)

        await callback.answer("Время изменено. Перезапустите планировщик для применения изменений.")
        await callback_admin_features(callback, state)
    except Exception:
        logger.error("Error in callback_change_time")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


# CHANGE DAYS MENU
@admin_router.callback_query(F.data == "change_days")
async def callback_change_days(callback: CallbackQuery, state: FSMContext):
    try:
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
    except Exception:
        logger.error("Error in callback_change_days")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


# SELECT DAY
@admin_router.callback_query(F.data.startswith("change_day_"))
async def callback_change_day_status(callback: CallbackQuery, state: FSMContext):
    try:
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

        await callback.answer("День изменен. Перезапустите планировщик для применения изменений.")
        await callback_change_days(callback, state)
    except Exception:
        logger.error("Error in callback_change_day_status")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


@admin_router.callback_query(F.data == "statistics")
async def callback_statistics(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    try:
        await state.clear()

        users = await orm.orm_read(session=session, model=User, as_iterable=True)
        users_btns = {}

        for user in users:
            users_btns[user.username if user.username else user.telegram_id] = (
                f"statistics_{user.pk}"
            )

        users_btns["Назад"] = "admin"

        await callback.message.edit_text(
            text="Статистика пользователей",
            reply_markup=get_callback_btns(btns=users_btns, sizes=(1, 2)),
        )
    except Exception:
        logger.error("Error in callback_statistics")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


@admin_router.callback_query(F.data.startswith("statistics_"))
async def callback_statistics(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    try:
        user_pk = int(callback.data.split("_")[1])
        user = await orm.orm_read(session=session, model=User, pk=user_pk)

        telegram_id = f"ID: {user.tg_id}"
        username = (
            f"Юзернейм: {f'@{user.username}' if user.username else 'Нет юзернейма'}"
        )
        subscription = f"Подписка: {'✅' if user.subscription else '❌'}"
        last_request = f"Последний запрос: {user.last_request.strftime('%H:%M %d-%m-%Y') if user.last_request else 'Нет запросов'}"

        btns = get_callback_btns(
            btns={
                "Последние запросы": f"requests_statistics_{user_pk}",
                "Назад": "statistics",
            },
            sizes=(1,),
        )

        await callback.message.edit_text(
            text=f"{telegram_id}\n{username}\n{subscription}\n{last_request}",
            reply_markup=btns,
        )
    except Exception:
        logger.error("Error in callback_statistics")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


@admin_router.callback_query(F.data.startswith("requests_statistics_"))
async def callback_statistics_requests(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    try:
        user_pk = int(callback.data.split("_")[2])
        user = await orm.orm_read(session=session, model=User, pk=user_pk)
        sorted_data = dict(
            sorted(
                user.cards.items(),
                key=lambda item: datetime.fromisoformat(item[1]),
                reverse=True,
            )
        )
        sorted_data = dict(list(sorted_data.items())[:10])
        text = f"Последние запросы пользователя: {f'@{user.username}' if user.username else user.tg_id}\n\n"

        for key, value in sorted_data.items():
            dt = datetime.fromisoformat(value)
            formatted_date = dt.strftime("%H:%M %d-%m-%Y")
            card = await orm.orm_read(session=session, model=Card, pk=int(key))
            text += f"{formatted_date}: {card.description[:40]}{'...' if card.description and len(card.description) > 40 else ''}\n"

        await callback.message.edit_text(
            text=text,
            reply_markup=get_callback_btns(
                btns={"Назад": f"statistics_{user_pk}"}, sizes=(1,)
            ),
        )
    except Exception:
        logger.error("Error in callback_statistics")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


class ChangeLimits(StatesGroup):
    limit = State()


@admin_router.callback_query(F.data == "edit_limits")
async def callback_edit_limits(callback: CallbackQuery, state: FSMContext):
    try:
        with open("config.json", "r") as f:
            data = json.load(f)

        cards_limit = data.get("cards_limit")

        await callback.message.edit_text(
            text=f"Введите лимит карточек. Текущий лимит: {cards_limit if cards_limit else 3}",
            reply_markup=get_callback_btns(btns={"Назад": "admin"}, sizes=(1,)),
        )
        await state.set_state(ChangeLimits.limit)
    except Exception:
        logger.error("Error in callback_edit_limits")
        logger.error(traceback.format_exc())
        await callback.message.answer("Произошла ошибка 😞...")


@admin_router.message(ChangeLimits.limit)
async def callback_change_limits(message: Message, state: FSMContext):
    try:
        limit = message.text

        if limit.isdigit():
            limit = int(limit)
        else:
            await message.answer(
                "Введите корректное число. Например: 5, 3, 2",
                reply_markup=get_callback_btns(
                    btns={"Назад": "edit_limits"}, sizes=(1,)
                ),
            )
            await state.set_state(ChangeLimits.limit)
            return

        with open("config.json", "r") as f:
            data = json.load(f)

        data["cards_limit"] = limit

        with open("config.json", "w") as f:
            json.dump(data, f)

        await message.answer(text="Лимит изменен")
        await admin_features(message, state)
    except Exception:
        logger.error("Error in callback_change_limits")
        logger.error(traceback.format_exc())
        await message.answer("Произошла ошибка 😞...")


class ChangeHelp(StatesGroup):
    help = State()

@admin_router.callback_query(F.data == "edit_help")
async def callback_edit_help(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Введите текст для помощи", reply_markup=get_callback_btns(btns={"Назад": "admin"}, sizes=(1,)))
    await state.set_state(ChangeHelp.help)

@admin_router.message(ChangeHelp.help)
async def callback_change_help(message: Message, state: FSMContext):
    with open("config.json", "r") as f:
        data = json.load(f)

    data["help_text"] = message.text

    with open("config.json", "w") as f:
        json.dump(data, f)

    await message.answer("Текст изменен")
    await state.clear()
    await admin_features(message, state)


class ChangeStart(StatesGroup):
    start = State()

@admin_router.callback_query(F.data == "edit_start")
async def callback_edit_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Введите текст для стартового сообщения", reply_markup=get_callback_btns(btns={"Назад": "admin"}, sizes=(1,)))
    await state.set_state(ChangeStart.start)

@admin_router.message(ChangeStart.start)
async def callback_change_start(message: Message, state: FSMContext):
    with open("config.json", "r") as f:
        data = json.load(f)

    data["start_text"] = message.text

    with open("config.json", "w") as f:
        json.dump(data, f)

    await message.answer("Текст изменен")
    await state.clear()
    await admin_features(message, state)