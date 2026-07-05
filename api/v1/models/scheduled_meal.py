import enum
from datetime import datetime, date
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.v1.models.base_class import Base


class MealType(str, enum.Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class ScheduledMeal(Base):
    __tablename__ = "scheduled_meals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    meal_type: Mapped[MealType] = mapped_column(String(20), nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="scheduled", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="scheduled_meals")
    vendor: Mapped[Optional["Vendor"]] = relationship(back_populates="scheduled_meals")
