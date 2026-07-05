from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from api.v1.models.scheduled_meal import MealType


class ScheduledMealCreate(BaseModel):
    user_id: int
    meal_type: MealType
    delivery_date: date
    delivery_time: datetime
    vendor_id: Optional[int] = None
    status: str = "scheduled"


class ScheduledMealRead(ScheduledMealCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
