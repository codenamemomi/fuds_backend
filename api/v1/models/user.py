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
    otp: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    diet_goal: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    scheduled_meals: Mapped[list["ScheduledMeal"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    marketplace_items: Mapped[list["Marketplace"]] = relationship(back_populates="user", cascade="all, delete-orphan")
