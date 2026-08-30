from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.v1.models.scheduled_meal import MealType


class ScheduledMealCreate(BaseModel):
    meal_type: MealType
    delivery_date: date
    slot_time: str = Field(..., description="HH:MM 24-hour time inside the meal window")
    product_id: Optional[int] = None
    quantity: int = Field(default=1, ge=1, le=20)

    @field_validator("slot_time")
    @classmethod
    def normalize_slot_time(cls, value: str) -> str:
        text = (value or "").strip()
        try:
            datetime.strptime(text, "%H:%M")
        except ValueError as exc:
            raise ValueError("slot_time must be HH:MM (e.g. 08:30)") from exc
        return text


class ScheduledMealUpdate(BaseModel):
    slot_time: Optional[str] = Field(None, description="HH:MM 24-hour time inside the meal window")
    product_id: Optional[int] = None
    quantity: Optional[int] = Field(None, ge=1, le=20)
    clear_product: bool = False

    @field_validator("slot_time")
    @classmethod
    def normalize_slot_time(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        text = value.strip()
        try:
            datetime.strptime(text, "%H:%M")
        except ValueError as exc:
            raise ValueError("slot_time must be HH:MM (e.g. 08:30)") from exc
        return text


class ScheduledMealRead(BaseModel):
    id: int
    user_id: int
    meal_type: MealType
    delivery_date: date
    delivery_time: datetime
    slot_time: str
    vendor_id: Optional[int] = None
    product_id: Optional[int] = None
    quantity: int = 1
    order_id: Optional[int] = None
    status: str
    created_at: datetime
    product_name: Optional[str] = None
    product_price: Optional[float] = None
    product_image_url: Optional[str] = None
    vendor_name: Optional[str] = None
    subtotal: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class MealWindowRead(BaseModel):
    meal_type: MealType
    label: str
    start: str
    end: str
    range_label: str
    slot_times: list[str]


class ScheduleDayRead(BaseModel):
    date: date
    weekday: str
    label: str
    is_today: bool
    is_past: bool
    available_slots: dict[str, list[str]]
    meals: dict[str, list[ScheduledMealRead]]


class ScheduleWeekRead(BaseModel):
    timezone: str
    windows: list[MealWindowRead]
    days: list[ScheduleDayRead]


class ScheduleCheckoutRequest(BaseModel):
    delivery_date: date
    meal_types: Optional[list[MealType]] = None
