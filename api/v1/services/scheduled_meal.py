from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from api.v1.models.order import Order
from api.v1.models.order_item import OrderItem
from api.v1.models.product import Product
from api.v1.models.scheduled_meal import (
    LAGOS_TZ,
    MEAL_WINDOW_LABELS,
    MEAL_WINDOWS,
    WEEKDAY_LABELS,
    WEEKDAY_NAMES,
    MealType,
    ScheduledMeal,
    coerce_meal_type,
    format_slot,
    meal_slot_times,
    now_lagos,
    parse_slot_time,
    rolling_week_dates,
)
from api.v1.schema.order import OrderRead
from api.v1.schema.scheduled_meal import (
    MealWindowRead,
    ScheduleCheckoutRequest,
    ScheduleDayRead,
    ScheduledMealCreate,
    ScheduledMealRead,
    ScheduledMealUpdate,
    ScheduleWeekRead,
)
from api.v1.services.base import BaseService
from api.v1.services.order import OrderService


class ScheduledMealService(BaseService[ScheduledMeal, ScheduledMealCreate, ScheduledMealRead]):
    def __init__(self, db: Session):
        super().__init__(ScheduledMeal, db)

    def list_windows(self) -> list[MealWindowRead]:
        return [_window_payload(meal) for meal in MealType]

    def get_week(self, user_id: int, start: date | None = None) -> ScheduleWeekRead:
        today = now_lagos().date()
        days = rolling_week_dates(start or today)
        meals = (
            self.db.query(ScheduledMeal)
            .options(joinedload(ScheduledMeal.product), joinedload(ScheduledMeal.vendor))
            .filter(
                ScheduledMeal.user_id == user_id,
                ScheduledMeal.delivery_date.in_(days),
                ScheduledMeal.status != "cancelled",
            )
            .all()
        )
        by_key: dict[tuple[date, str], list[ScheduledMeal]] = {}
        for meal in meals:
            by_key.setdefault((meal.delivery_date, _meal_type_value(meal.meal_type)), []).append(meal)

        day_payloads: list[ScheduleDayRead] = []
        for day in days:
            weekday_index = day.weekday()
            meals_for_day: dict[str, list[ScheduledMealRead]] = {}
            available: dict[str, list[str]] = {}
            for meal_type in MealType:
                key = meal_type.value
                rows = sorted(
                    by_key.get((day, key), []),
                    key=lambda row: (row.delivery_time, row.id),
                )
                meals_for_day[key] = [self._to_read(row) for row in rows]
                available[key] = available_slot_times(meal_type, day)
            day_payloads.append(
                ScheduleDayRead(
                    date=day,
                    weekday=WEEKDAY_NAMES[weekday_index],
                    label=WEEKDAY_LABELS[weekday_index],
                    is_today=day == today,
                    is_past=day < today,
                    available_slots=available,
                    meals=meals_for_day,
                )
            )

        return ScheduleWeekRead(
            timezone="Africa/Lagos",
            windows=self.list_windows(),
            days=day_payloads,
        )

    def list_for_user(
        self,
        user_id: int,
        delivery_date: date | None = None,
    ) -> list[ScheduledMealRead]:
        query = (
            self.db.query(ScheduledMeal)
            .options(joinedload(ScheduledMeal.product), joinedload(ScheduledMeal.vendor))
            .filter(ScheduledMeal.user_id == user_id, ScheduledMeal.status != "cancelled")
        )
        if delivery_date is not None:
            query = query.filter(ScheduledMeal.delivery_date == delivery_date)
        rows = query.order_by(ScheduledMeal.delivery_date, ScheduledMeal.delivery_time).all()
        return [self._to_read(row) for row in rows]

    def create_meal(self, user_id: int, payload: ScheduledMealCreate) -> ScheduledMealRead:
        slot = parse_slot_time(payload.slot_time)
        self._assert_slot(payload.meal_type, payload.delivery_date, slot)
        product, vendor_id = self._resolve_product(payload.product_id)

        meal = ScheduledMeal(
            user_id=user_id,
            meal_type=payload.meal_type.value,
            delivery_date=payload.delivery_date,
            delivery_time=datetime.combine(payload.delivery_date, slot),
            product_id=product.id if product else None,
            vendor_id=vendor_id,
            quantity=payload.quantity,
            status="scheduled",
        )
        self.db.add(meal)
        self.db.commit()
        return self._reload(meal.id)

    def update_meal(self, user_id: int, meal_id: int, payload: ScheduledMealUpdate) -> ScheduledMealRead:
        meal = self._owned(user_id, meal_id)
        if meal.status == "confirmed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This meal slot is already checked out",
            )

        slot = parse_slot_time(payload.slot_time) if payload.slot_time else meal.delivery_time.time()
        meal_type = coerce_meal_type(meal.meal_type)
        self._assert_slot(meal_type, meal.delivery_date, slot)
        meal.delivery_time = datetime.combine(meal.delivery_date, slot)

        if payload.clear_product:
            meal.product_id = None
            meal.vendor_id = None
        elif payload.product_id is not None:
            product, vendor_id = self._resolve_product(payload.product_id)
            meal.product_id = product.id if product else None
            meal.vendor_id = vendor_id

        if payload.quantity is not None:
            meal.quantity = payload.quantity

        meal.status = "scheduled"
        self.db.commit()
        return self._reload(meal.id)

    def cancel(self, user_id: int, meal_id: int) -> None:
        meal = self._owned(user_id, meal_id)
        if meal.status == "confirmed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Checked-out meals cannot be removed from 111",
            )
        self.db.delete(meal)
        self.db.commit()

    def checkout(self, user_id: int, payload: ScheduleCheckoutRequest) -> OrderRead:
        wanted = {m.value for m in payload.meal_types} if payload.meal_types else None
        query = (
            self.db.query(ScheduledMeal)
            .options(joinedload(ScheduledMeal.product), joinedload(ScheduledMeal.vendor))
            .filter(
                ScheduledMeal.user_id == user_id,
                ScheduledMeal.delivery_date == payload.delivery_date,
                ScheduledMeal.status != "cancelled",
            )
        )
        meals = query.order_by(ScheduledMeal.delivery_time).all()
        if wanted:
            meals = [m for m in meals if _meal_type_value(m.meal_type) in wanted]

        ready = [m for m in meals if m.product_id and m.status != "confirmed"]
        if not ready:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Add a meal to at least one 111 slot before checkout",
            )

        for meal in ready:
            slot = meal.delivery_time.time().replace(second=0, microsecond=0)
            self._assert_slot(coerce_meal_type(meal.meal_type), meal.delivery_date, slot)
            if not meal.product:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{_meal_type_value(meal.meal_type)} is missing a product",
                )

        parent = Order(
            user_id=user_id,
            status="pending",
            payment_status="pending",
            total_price=0,
            delivery_time=ready[0].delivery_time,
            created_at=datetime.utcnow(),
        )
        self.db.add(parent)
        self.db.flush()

        grand_total = 0.0
        for meal in ready:
            product = meal.product
            qty = meal.quantity or 1
            price = float(product.price)
            subtotal = round(price * qty, 2)
            grand_total += subtotal
            sub_order = Order(
                user_id=user_id,
                parent_order_id=parent.id,
                vendor_id=product.vendor_id,
                status="pending",
                payment_status="pending",
                total_price=subtotal,
                delivery_time=meal.delivery_time,
                created_at=datetime.utcnow(),
            )
            self.db.add(sub_order)
            self.db.flush()
            self.db.add(
                OrderItem(
                    order_id=sub_order.id,
                    vendor_id=product.vendor_id,
                    product_id=product.id,
                    quantity=qty,
                    price=price,
                )
            )
            meal.order_id = parent.id
            meal.status = "confirmed"
            meal.vendor_id = product.vendor_id

        parent.total_price = round(grand_total, 2)
        self.db.commit()
        self.db.refresh(parent)
        return OrderService(self.db)._serialize_order(parent)

    def _assert_slot(self, meal_type: MealType | str, delivery_date: date, slot: time) -> None:
        meal = coerce_meal_type(meal_type)
        start, end = MEAL_WINDOWS[meal]
        if slot not in set(meal_slot_times(meal)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"{meal.value.title()} must be a 30-minute slot between "
                    f"{MEAL_WINDOW_LABELS[meal]}"
                ),
            )
        if not (start <= slot <= end):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{meal.value.title()} window is {MEAL_WINDOW_LABELS[meal]}",
            )

        today = now_lagos().date()
        if delivery_date < today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot schedule meals in the past",
            )

        delivery_dt = datetime.combine(delivery_date, slot, tzinfo=LAGOS_TZ)
        if delivery_dt < now_lagos() - timedelta(minutes=1):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That delivery slot has already passed",
            )

    def _resolve_product(self, product_id: int | None) -> tuple[Product | None, int | None]:
        if product_id is None:
            return None, None
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        return product, product.vendor_id

    def _owned(self, user_id: int, meal_id: int) -> ScheduledMeal:
        meal = (
            self.db.query(ScheduledMeal)
            .options(joinedload(ScheduledMeal.product), joinedload(ScheduledMeal.vendor))
            .filter(ScheduledMeal.id == meal_id, ScheduledMeal.user_id == user_id)
            .first()
        )
        if not meal or meal.status == "cancelled":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled meal not found")
        return meal

    def _reload(self, meal_id: int) -> ScheduledMealRead:
        meal = (
            self.db.query(ScheduledMeal)
            .options(joinedload(ScheduledMeal.product), joinedload(ScheduledMeal.vendor))
            .filter(ScheduledMeal.id == meal_id)
            .first()
        )
        if not meal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled meal not found")
        return self._to_read(meal)

    def _to_read(self, meal: ScheduledMeal) -> ScheduledMealRead:
        slot = meal.delivery_time.strftime("%H:%M") if meal.delivery_time else ""
        price = float(meal.product.price) if meal.product else None
        qty = meal.quantity or 1
        return ScheduledMealRead(
            id=meal.id,
            user_id=meal.user_id,
            meal_type=coerce_meal_type(meal.meal_type),
            delivery_date=meal.delivery_date,
            delivery_time=meal.delivery_time,
            slot_time=slot,
            vendor_id=meal.vendor_id,
            product_id=meal.product_id,
            quantity=qty,
            order_id=meal.order_id,
            status=meal.status,
            created_at=meal.created_at,
            product_name=meal.product.name if meal.product else None,
            product_price=price,
            product_image_url=meal.product.image_url if meal.product else None,
            vendor_name=meal.vendor.business_name if meal.vendor else None,
            subtotal=round(price * qty, 2) if price is not None else None,
        )


def available_slot_times(meal_type: MealType, day: date, now: datetime | None = None) -> list[str]:
    current = now or now_lagos()
    today = current.date()
    slots = meal_slot_times(meal_type)
    if day < today:
        return []
    if day > today:
        return [format_slot(slot) for slot in slots]
    cutoff = current.replace(second=0, microsecond=0)
    open_slots: list[str] = []
    for slot in slots:
        slot_dt = datetime.combine(day, slot, tzinfo=LAGOS_TZ)
        if slot_dt >= cutoff:
            open_slots.append(format_slot(slot))
    return open_slots


def _window_payload(meal_type: MealType) -> MealWindowRead:
    start, end = MEAL_WINDOWS[meal_type]
    return MealWindowRead(
        meal_type=meal_type,
        label=meal_type.value.title(),
        start=format_slot(start),
        end=format_slot(end),
        range_label=MEAL_WINDOW_LABELS[meal_type],
        slot_times=[format_slot(slot) for slot in meal_slot_times(meal_type)],
    )


def _meal_type_value(value: MealType | str) -> str:
    return coerce_meal_type(value).value
