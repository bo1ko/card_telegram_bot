from sqlalchemy import DateTime, Float, String, Text, BigInteger, func, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime


class Base(DeclarativeBase):
    created: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated: Mapped[DateTime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )


class User(Base):
    __tablename__ = "user"

    pk: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    subscription: Mapped[bool] = mapped_column(default=False)
    last_request: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    requests: Mapped[list] = mapped_column(JSON, default=list, nullable=True)
    cards: Mapped[dict] = mapped_column(JSON, default=dict, nullable=True)


class Card(Base):
    __tablename__ = "card"

    pk: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(Text)
    image: Mapped[str] = mapped_column(String(100))
