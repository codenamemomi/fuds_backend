import enum
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.v1.models.base_class import Base

LAGOS_TZ = ZoneInfo("Africa/Lagos")
SLOT_STEP_MINUTES = 30
WEEKDAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class MealType(str, enum.Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


# Inclusive windows in Africa/Lagos. Users pick any 30-minute slot inside.
MEAL_WINDOWS: dict[MealType, tuple[time, time]] = {
    MealType.BREAKFAST: (time(8, 0), time(11, 0)),
    MealType.LUNCH: (time(13, 0), time(16, 0)),
    MealType.DINNER: (time(17, 0), time(19, 0)),
}

MEAL_WINDOW_LABELS: dict[MealType, str] = {
    MealType.BREAKFAST: "8:00 AM – 11:00 AM",
    MealType.LUNCH: "1:00 PM – 4:00 PM",
    MealType.DINNER: "5:00 PM – 7:00 PM",
}


def now_lagos() -> datetime:
    return datetime.now(LAGOS_TZ)


def coerce_meal_type(value: MealType | str) -> MealType:
    if isinstance(value, MealType):
        return value
    return MealType(str(value).strip().lower())


def meal_slot_times(meal_type: MealType | str) -> list[time]:
    """30-minute delivery options inside the meal window, inclusive."""
    meal = coerce_meal_type(meal_type)
    start, end = MEAL_WINDOWS[meal]
    slots: list[time] = []
    cursor = datetime.combine(date(2000, 1, 1), start)
    last = datetime.combine(date(2000, 1, 1), end)
    while cursor <= last:
        slots.append(cursor.time().replace(second=0, microsecond=0))
        cursor += timedelta(minutes=SLOT_STEP_MINUTES)
    return slots


def format_slot(slot: time) -> str:
    return slot.strftime("%H:%M")


def parse_slot_time(value: str) -> time:
    text = (value or "").strip()
    try:
        parsed = datetime.strptime(text, "%H:%M").time()
    except ValueError as exc:
        raise ValueError("Delivery time must be HH:MM (24-hour, e.g. 08:30)") from exc
    return parsed.replace(second=0, microsecond=0)


def rolling_week_dates(today: date | None = None) -> list[date]:
    """Next 7 calendar days starting today (covers Mon–Sun)."""
    start = today or now_lagos().date()
    return [start + timedelta(days=offset) for offset in range(7)]


class ScheduledMeal(Base):
    __tablename__ = "scheduled_meals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    meal_type: Mapped[MealType] = mapped_column(String(20), nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="scheduled", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="scheduled_meals")
    vendor: Mapped[Optional["Vendor"]] = relationship(back_populates="scheduled_meals")
    product: Mapped[Optional["Product"]] = relationship()
    order: Mapped[Optional["Order"]] = relationship()
