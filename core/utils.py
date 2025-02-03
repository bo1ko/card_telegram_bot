import json
import re

from sqlalchemy.ext.asyncio import AsyncSession
from bs4 import BeautifulSoup

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

    if user and not user.subscription:
        sub_text = "🔔 Подписаться на ежедневную карту 🔔"
        sub_callback = "subscribe"
    else:
        sub_text = "❌ Відписатися від щоденної карти ❌"
        sub_callback = "unsubscribe"

    main_menu_btns = get_inlineMix_btns(
        btns={
            "Хочу карту дня 🔮": "card",
            "Купить колоду 🛒": buy_cards_link,
            "📖 Информация о боте 📖": "help",
            "🃏 Дать полный расклад карт 🃏": full_card_link,
            sub_text: sub_callback,
        },
        sizes=(2, 1),
    )

    return main_menu_btns


def clean_html(input_text):
    allowed_tags = [
        "b",
        "strong",
        "i",
        "em",
        "u",
        "ins",
        "s",
        "strike",
        "del",
        "tg-spoiler",
        "code",
        "pre",
        "a",
    ]
    allowed_attributes = {"a": ["href"]}

    soup = BeautifulSoup(input_text, "html.parser")

    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            if (
                tag.name == "span"
                and tag.get("class")
                and "tg-spoiler" in tag.get("class")
            ):
                tag.name = "tg-spoiler"
            else:
                tag.unwrap()
        elif tag.name == "a":
            tag.attrs = {
                key: value
                for key, value in tag.attrs.items()
                if key in allowed_attributes.get(tag.name, [])
            }

    return str(soup)
