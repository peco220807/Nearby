import secrets
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def new_token() -> str:
    return secrets.token_urlsafe(16)


class Household(Base):
    __tablename__ = "households"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    parent_name: Mapped[str | None] = mapped_column(String(120))
    share_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=new_token)

    members: Mapped[list["Member"]] = relationship(back_populates="household", order_by="Member.id")


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))

    household: Mapped[Household] = relationship(back_populates="members")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    paid_by_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)  # деньги только в центах
    category: Mapped[str] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(String(200))
    expense_date: Mapped[date] = mapped_column(Date)
    split_mode: Mapped[str] = mapped_column(String(20), default="equal")


class ExpenseShare(Base):
    __tablename__ = "expense_shares"

    id: Mapped[int] = mapped_column(primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    share_cents: Mapped[int] = mapped_column(Integer)


class CareEntry(Base):
    __tablename__ = "care_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    hours: Mapped[float] = mapped_column(Float)
    entry_date: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(200))
