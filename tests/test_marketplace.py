"""FUDS Marketplace — grocery aisles and recurring rosters."""

from datetime import time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.db.session import get_db
from api.v1.models import Base
from api.v1.models.product import Product
from api.v1.models.scheduled_meal import now_lagos
from api.v1.models.vendor import Vendor, VendorStatus
from main import app

engine = create_engine(
    "sqlite:///:memory:",
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


@pytest.fixture(scope="module")
def token(client: TestClient) -> str:
    import json

    from api.utils.redis_utils import redis_client

    client.post(
        "/api/v1/auth/register",
        json={
            "fullname": "Market Tester",
            "phone": "08033335555",
            "email": "market111@example.com",
            "password": "Secret123",
            "password_confirm": "Secret123",
        },
    )
    otp_raw = redis_client.get("otp:registration:market111@example.com")
    otp_code = json.loads(otp_raw)["code"]
    client.post("/api/v1/auth/verify-otp", json={"email": "market111@example.com", "otp": otp_code})
    resp = client.post("/api/v1/auth/login", json={"phone": "08033335555", "password": "Secret123"})
    return resp.json()["access_token"]


def seed_groceries() -> Product:
    db = TestingSessionLocal()
    try:
        existing = db.query(Product).filter(Product.name == "Milo Refill (400g)").first()
        if existing:
            return existing
        vendor = Vendor(
            business_name="MartPlus Supermarket",
            category="supermarket",
            status=VendorStatus.ACTIVATED,
            opening_time=time(8, 0),
            closing_time=time(21, 0),
        )
        db.add(vendor)
        db.flush()
        milo = Product(
            vendor_id=vendor.id,
            name="Milo Refill (400g)",
            price=3200,
            category="supermarket",
            aisle="beverages",
        )
        milk = Product(
            vendor_id=vendor.id,
            name="Peak Milk (1L carton)",
            price=1800,
            category="supermarket",
            aisle="dairy",
        )
        cereal = Product(
            vendor_id=vendor.id,
            name="Golden Morn (1kg)",
            price=2200,
            category="supermarket",
            aisle="cereals",
        )
        db.add_all([milo, milk, cereal])
        db.commit()
        db.refresh(milo)
        return milo
    finally:
        db.close()


class TestMarketplaceCatalog:
    def test_aisles_include_milo_milk_cereals(self, client):
        seed_groceries()
        resp = client.get("/api/v1/marketplace/aisles")
        assert resp.status_code == 200
        keys = {row["key"] for row in resp.json()}
        assert {"beverages", "dairy", "cereals", "staples", "fresh"}.issubset(keys)

    def test_catalog_filter_by_aisle(self, client):
        seed_groceries()
        resp = client.get("/api/v1/marketplace/catalog?aisle=beverages")
        assert resp.status_code == 200
        body = resp.json()
        assert body["products"]
        assert all(p["aisle"] == "beverages" for p in body["products"])
        assert any("Milo" in p["name"] for p in body["products"])


class TestGroceryRoster:
    def test_create_schedule_and_checkout(self, client, token):
        milo = seed_groceries()
        headers = {"Authorization": f"Bearer {token}"}
        day = (now_lagos().date() + timedelta(days=2)).isoformat()
        created = client.post(
            "/api/v1/marketplace/subscriptions",
            headers=headers,
            json={
                "frequency": "weekly",
                "next_delivery": day,
                "items": [{"product_id": milo.id, "quantity": 2}],
            },
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["frequency"] == "weekly"
        assert body["item_count"] == 2
        assert body["total"] == 6400
        assert body["items"][0]["name"] == "Milo Refill (400g)"

        checkout = client.post(
            f"/api/v1/marketplace/subscriptions/{body['id']}/checkout",
            headers=headers,
        )
        assert checkout.status_code == 201, checkout.text
        order = checkout.json()
        assert float(order["total_price"]) == 6400
        assert order["payment_status"] == "pending"
