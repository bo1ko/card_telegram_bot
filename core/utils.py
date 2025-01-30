import json

from sqlalchemy.ext.asyncio import AsyncSession

from core.keyboards import get_inlineMix_btns
from core.database.models import User
from core.database import orm_query as orm


async def generate_main_menu(telegram_id: int, session: AsyncSession):
    user = await orm.orm_read(session=session, model=User, tg_id=telegram_id)
    sub_text = ""
    sub_callback = ""

    with open("config.json", "r") as f:
        data = json.load(f)

    if data.get("buy_cards_link"):
        buy_cards_link = data["buy_cards_link"]
    else:
        buy_cards_link = "https://example.com/"

    if data.get("full_card_link"):
        full_card_link = data["full_card_link"]
    else:
        full_card_link = "https://example.com/"

    if not user.subscription:
        sub_text = "📩 Подписаться на ежедневную карту 📩"
        sub_callback = "subscribe"
    else:
        sub_text = "❌ Відписатися від щоденної карти ❌"
        sub_callback = "unsubscribe"

    main_menu_btns = get_inlineMix_btns(
        btns={
            "Карта дня 🔮": "card",
            "Купить карты 🛒": buy_cards_link,
            "🃏 Дать полный расклад карт 🃏": full_card_link,
            sub_text: sub_callback,
        },
        sizes=(2, 1),
    )

    return main_menu_btns
