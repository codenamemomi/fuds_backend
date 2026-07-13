from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.v1.models.base_class import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    fullname: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    diet_goal: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Paystack customer + Titan dedicated virtual account (pay-with-transfer)
    paystack_customer_code: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    paystack_dva_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    paystack_dva_account_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    paystack_dva_account_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    paystack_dva_bank_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    paystack_dva_bank_slug: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    orders: Mapped[list["Order"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    scheduled_meals: Mapped[list["ScheduledMeal"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    grocery_subscriptions: Mapped[list["GrocerySubscription"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def marketplace_items(self):
        return self.grocery_subscriptions

    @marketplace_items.setter
    def marketplace_items(self, value):
        self.grocery_subscriptions = value
