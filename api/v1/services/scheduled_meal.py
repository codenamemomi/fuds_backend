from sqlalchemy.orm import Session

from api.v1.models.scheduled_meal import ScheduledMeal
from api.v1.schema.scheduled_meal import ScheduledMealCreate, ScheduledMealRead
from api.v1.services.base import BaseService


class ScheduledMealService(BaseService[ScheduledMeal, ScheduledMealCreate, ScheduledMealRead]):
    def __init__(self, db: Session):
        super().__init__(ScheduledMeal, db)
