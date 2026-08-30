"""111 meal scheduler: windows, weekday planning, upsert, checkout."""

from datetime import date, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.db.session import get_db
from api.v1.models import Base
from api.v1.models.product import Product
from api.v1.models.scheduled_meal import (
    MEAL_WINDOWS,
    MealType,
    meal_slot_times,
    now_lagos,
)
from api.v1.models.vendor import Vendor, VendorStatus
from api.v1.services.scheduled_meal import available_slot_times
from main import app

SQLITE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def future_date() -> date:
    return now_lagos().date() + timedelta(days=7)


@pytest.fixture(scope="module")
def token(client: TestClient) -> str:
    import json

    from api.utils.redis_utils import redis_client

    client.post(
        "/api/v1/auth/register",
        json={
            "fullname": "Schedule Tester",
            "phone": "08022224444",
            "email": "schedule111@example.com",
            "password": "Secret123",
            "password_confirm": "Secret123",
        },
    )
    otp_raw = redis_client.get("otp:registration:schedule111@example.com")
    otp_code = json.loads(otp_raw)["code"]
    client.post("/api/v1/auth/verify-otp", json={"email": "schedule111@example.com", "otp": otp_code})
    resp = client.post("/api/v1/auth/login", json={"phone": "08022224444", "password": "Secret123"})
    return resp.json()["access_token"]


def seed_product() -> Product:
    db = TestingSessionLocal()
    try:
        existing = db.query(Product).filter(Product.name == "Jollof Rice + Chicken").first()
        if existing:
            return existing
        vendor = Vendor(
            business_name="Mama Titi's Kitchen",
            category="restaurant",
            status=VendorStatus.ACTIVATED,
            opening_time=time(8, 0),
            closing_time=time(22, 0),
        )
        db.add(vendor)
        db.flush()
        product = Product(
            vendor_id=vendor.id,
            name="Jollof Rice + Chicken",
            price=2500,
            category="restaurant",
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        return product
    finally:
        db.close()


class TestMealWindows:
    def test_breakfast_lunch_dinner_bounds(self):
        assert MEAL_WINDOWS[MealType.BREAKFAST] == (time(8, 0), time(11, 0))
        assert MEAL_WINDOWS[MealType.LUNCH] == (time(13, 0), time(16, 0))
        assert MEAL_WINDOWS[MealType.DINNER] == (time(17, 0), time(19, 0))

    def test_breakfast_slots_are_half_hours_inside_window(self):
        slots = meal_slot_times(MealType.BREAKFAST)
        assert slots[0] == time(8, 0)
        assert slots[-1] == time(11, 0)
        assert time(7, 30) not in slots
        assert time(11, 30) not in slots
        assert all(slot.minute in (0, 30) for slot in slots)

    def test_past_slots_are_filtered_for_today(self):
        today = now_lagos().date()
        fake_now = now_lagos().replace(hour=10, minute=5, second=0, microsecond=0)
        slots = available_slot_times(MealType.BREAKFAST, today, now=fake_now)
        assert "08:00" not in slots
        assert "10:00" not in slots
        assert "10:30" in slots
        assert "11:00" in slots


class TestScheduleApi:
    def test_windows_endpoint(self, client):
        resp = client.get("/api/v1/schedule/windows")
        assert resp.status_code == 200
        body = resp.json()
        by_type = {row["meal_type"]: row for row in body}
        assert by_type["breakfast"]["start"] == "08:00"
        assert by_type["breakfast"]["end"] == "11:00"
        assert by_type["lunch"]["start"] == "13:00"
        assert by_type["lunch"]["end"] == "16:00"
        assert by_type["dinner"]["start"] == "17:00"
        assert by_type["dinner"]["end"] == "19:00"
        assert "09:30" in by_type["breakfast"]["slot_times"]
        assert "13:00" in by_type["lunch"]["slot_times"]
        assert "19:00" in by_type["dinner"]["slot_times"]

    def test_week_covers_seven_weekdays(self, client, token):
        resp = client.get("/api/v1/schedule/week", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["timezone"] == "Africa/Lagos"
        assert len(body["days"]) == 7
        weekdays = {day["weekday"] for day in body["days"]}
        assert weekdays == {
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        }
        assert body["days"][0]["is_today"] is True
        assert set(body["days"][0]["meals"]) == {"breakfast", "lunch", "dinner"}
        assert body["days"][0]["meals"]["breakfast"] == []

    def test_create_breakfast_inside_window(self, client, token):
        product = seed_product()
        day = future_date().isoformat()
        resp = client.post(
            "/api/v1/schedule",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "meal_type": "breakfast",
                "delivery_date": day,
                "slot_time": "09:00",
                "product_id": product.id,
                "quantity": 1,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["meal_type"] == "breakfast"
        assert body["slot_time"] == "09:00"
        assert body["product_name"] == "Jollof Rice + Chicken"
        assert body["subtotal"] == 2500

    def test_reject_lunch_outside_window(self, client, token):
        resp = client.post(
            "/api/v1/schedule",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "meal_type": "lunch",
                "delivery_date": future_date().isoformat(),
                "slot_time": "11:00",
            },
        )
        assert resp.status_code == 400
        assert "Lunch" in resp.json()["detail"]

    def test_reject_dinner_after_seven(self, client, token):
        resp = client.post(
            "/api/v1/schedule",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "meal_type": "dinner",
                "delivery_date": future_date().isoformat(),
                "slot_time": "19:30",
            },
        )
        assert resp.status_code == 400

    def test_can_schedule_multiple_meals_same_slot(self, client, token):
        product = seed_product()
        headers = {"Authorization": f"Bearer {token}"}
        day = (now_lagos().date() + timedelta(days=5)).isoformat()

        first = client.post(
            "/api/v1/schedule",
            headers=headers,
            json={
                "meal_type": "lunch",
                "delivery_date": day,
                "slot_time": "13:00",
                "product_id": product.id,
            },
        )
        assert first.status_code == 201, first.text

        second = client.post(
            "/api/v1/schedule",
            headers=headers,
            json={
                "meal_type": "lunch",
                "delivery_date": day,
                "slot_time": "13:00",
                "product_id": product.id,
                "quantity": 2,
            },
        )
        assert second.status_code == 201, second.text
        assert second.json()["id"] != first.json()["id"]
        assert second.json()["slot_time"] == "13:00"
        assert second.json()["quantity"] == 2

        dinner = client.post(
            "/api/v1/schedule",
            headers=headers,
            json={
                "meal_type": "dinner",
                "delivery_date": day,
                "slot_time": "18:00",
                "product_id": product.id,
            },
        )
        assert dinner.status_code == 201

        week = client.get("/api/v1/schedule/week", headers=headers)
        day_row = next(d for d in week.json()["days"] if d["date"] == day)
        assert len(day_row["meals"]["lunch"]) == 2
        assert len(day_row["meals"]["dinner"]) == 1

        checkout = client.post(
            "/api/v1/schedule/checkout",
            headers=headers,
            json={"delivery_date": day},
        )
        assert checkout.status_code == 201, checkout.text
        order = checkout.json()
        assert order["payment_status"] == "pending"
        assert float(order["total_price"]) == 10000
        assert len(order["items"]) == 3

        extra = client.post(
            "/api/v1/schedule",
            headers=headers,
            json={
                "meal_type": "lunch",
                "delivery_date": day,
                "slot_time": "15:30",
                "product_id": product.id,
            },
        )
        assert extra.status_code == 201, extra.text
        assert extra.json()["status"] == "scheduled"

    def test_checkout_without_meals_fails(self, client, token):
        resp = client.post(
            "/api/v1/schedule/checkout",
            headers={"Authorization": f"Bearer {token}"},
            json={"delivery_date": (now_lagos().date() + timedelta(days=9)).isoformat()},
        )
        assert resp.status_code == 400
