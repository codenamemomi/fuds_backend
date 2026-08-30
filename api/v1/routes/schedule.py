from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.v1.models.user import User
from api.v1.schema.order import OrderRead
from api.v1.schema.scheduled_meal import (
    MealWindowRead,
    ScheduleCheckoutRequest,
    ScheduledMealCreate,
    ScheduledMealRead,
    ScheduledMealUpdate,
    ScheduleWeekRead,
)
from api.v1.services.scheduled_meal import ScheduledMealService
from api.v1.services.user import UserService

router = APIRouter(prefix="/schedule", tags=["schedule"])
security = HTTPBearer()


def _get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = credentials.credentials
    if UserService.is_token_blacklisted(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is blacklisted")
    try:
        payload = UserService.decode_access_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def get_schedule_service(db: Session = Depends(get_db)) -> ScheduledMealService:
    return ScheduledMealService(db)


@router.get("/windows", response_model=list[MealWindowRead])
def list_meal_windows(service: ScheduledMealService = Depends(get_schedule_service)):
    """Breakfast 8–11am, lunch 1–4pm, dinner 5–7pm (Africa/Lagos), 30-minute slots."""
    return service.list_windows()


@router.get("/week", response_model=ScheduleWeekRead)
def get_schedule_week(
    start: Optional[date] = Query(None, description="First day of the rolling 7-day week"),
    current_user: User = Depends(_get_current_user),
    service: ScheduledMealService = Depends(get_schedule_service),
):
    """Next 7 days (Mon–Sun labels) with 111 slots and any meals already planned."""
    return service.get_week(current_user.id, start)


@router.get("", response_model=list[ScheduledMealRead])
def list_scheduled_meals(
    delivery_date: Optional[date] = Query(None),
    current_user: User = Depends(_get_current_user),
    service: ScheduledMealService = Depends(get_schedule_service),
):
    return service.list_for_user(current_user.id, delivery_date)


@router.post("", response_model=ScheduledMealRead, status_code=status.HTTP_201_CREATED)
def create_scheduled_meal(
    payload: ScheduledMealCreate,
    current_user: User = Depends(_get_current_user),
    service: ScheduledMealService = Depends(get_schedule_service),
):
    """Add a 111 meal. Users can add multiple dishes to the same window/time."""
    return service.create_meal(current_user.id, payload)


@router.patch("/{meal_id}", response_model=ScheduledMealRead)
def update_scheduled_meal(
    meal_id: int,
    payload: ScheduledMealUpdate,
    current_user: User = Depends(_get_current_user),
    service: ScheduledMealService = Depends(get_schedule_service),
):
    return service.update_meal(current_user.id, meal_id, payload)


@router.delete("/{meal_id}", status_code=status.HTTP_200_OK)
def delete_scheduled_meal(
    meal_id: int,
    current_user: User = Depends(_get_current_user),
    service: ScheduledMealService = Depends(get_schedule_service),
):
    service.cancel(current_user.id, meal_id)
    return {"message": "Scheduled meal removed"}


@router.post("/checkout", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def checkout_scheduled_meals(
    payload: ScheduleCheckoutRequest,
    current_user: User = Depends(_get_current_user),
    service: ScheduledMealService = Depends(get_schedule_service),
):
    """Turn filled 111 slots for a date into a parent order (one sub-order per meal)."""
    return service.checkout(current_user.id, payload)
