from sqlalchemy import DateTime, Float, String, Text, BigInteger, func, ForeignKey
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
    tg_id: Mapped[int] = mapped_column(unique=True)
    subscription: Mapped[bool] = mapped_column(default=False)
    requests: Mapped[int] = mapped_column(default=0)
    last_request: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    cards: Mapped[list["UserCard"]] = relationship(back_populates="user")


class Card(Base):
    __tablename__ = "card"

    pk: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(Text)
    image: Mapped[str] = mapped_column(String(100))
    users: Mapped[list["UserCard"]] = relationship(back_populates="card")


class UserCard(Base):
    __tablename__ = "user_card"

    pk: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.pk"))
    card_id: Mapped[int] = mapped_column(ForeignKey("card.pk"))

    user: Mapped["User"] = relationship(back_populates="cards")
    card: Mapped["Card"] = relationship(back_populates="users")
