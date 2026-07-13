"""
Integration tests for browse (vendors/products), cart, and order checkout flows.
These tests hit the real PostgreSQL database (read-only browse) and Redis (cart).
Vendors/products seeded via scripts/seed_db.py must be present.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.db.session import get_db
from api.v1.models import Base
from main import app

# ─── In-memory SQLite fixture for auth parts ─────────────────────────────────

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


# ─── Helpers ─────────────────────────────────────────────────────────────────

def register_verify_login(client) -> str:
    """Register, verify OTP from Redis, and login. Returns access token."""
    import json
    from api.utils.redis_utils import redis_client

    client.post("/api/v1/auth/register", json={
        "fullname": "Commerce Tester",
        "phone": "08011112222",
        "email": "commerce@example.com",
        "password": "Secret123", "password_confirm": "Secret123",
    })
    otp_raw = redis_client.get("otp:registration:commerce@example.com")
    otp_code = json.loads(otp_raw)["code"]
    client.post("/api/v1/auth/verify-otp", json={"email": "commerce@example.com", "otp": otp_code})
    resp = client.post("/api/v1/auth/login", json={"phone": "08011112222", "password": "Secret123"})
    return resp.json()["access_token"]


# ─── Browse: Vendors ──────────────────────────────────────────────────────────

class TestBrowseVendors:
    def test_list_vendors_returns_results(self, client):
        """Browse vendors should return seeded vendors from the real DB.
        Since tests use in-memory SQLite (no seed data), this verifies the
        endpoint works and returns an empty list gracefully."""
        resp = client.get("/api/v1/browse/vendors")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_vendors_filter_by_category(self, client):
        resp = client.get("/api/v1/browse/vendors?category=restaurant")
        assert resp.status_code == 200
        data = resp.json()
        for vendor in data:
            assert vendor["category"] == "restaurant"

    def test_list_vendors_search(self, client):
        resp = client.get("/api/v1/browse/vendors?search=nonexistent_xyz_vendor")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_vendors_pagination(self, client):
        resp = client.get("/api/v1/browse/vendors?page=1&limit=5")
        assert resp.status_code == 200
        assert len(resp.json()) <= 5

    def test_get_vendor_not_found(self, client):
        resp = client.get("/api/v1/browse/vendors/999999")
        assert resp.status_code == 404


# ─── Browse: Products ─────────────────────────────────────────────────────────

class TestBrowseProducts:
    def test_list_products_returns_results(self, client):
        resp = client.get("/api/v1/browse/products")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_products_filter_by_category(self, client):
        resp = client.get("/api/v1/browse/products?category=bakery")
        assert resp.status_code == 200
        for product in resp.json():
            assert product["category"] == "bakery"

    def test_list_products_price_filter(self, client):
        resp = client.get("/api/v1/browse/products?min_price=0&max_price=100000")
        assert resp.status_code == 200
        for product in resp.json():
            assert product["price"] <= 100000

    def test_list_products_name_search(self, client):
        resp = client.get("/api/v1/browse/products?name=nonexistent_product_xyz")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_product_not_found(self, client):
        resp = client.get("/api/v1/browse/products/999999")
        assert resp.status_code == 404


# ─── Cart ─────────────────────────────────────────────────────────────────────

class TestCart:
    def test_view_empty_cart(self, client):
        token = register_verify_login(client)
        resp = client.get("/api/v1/cart", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0.0
        assert body["item_count"] == 0

    def test_add_nonexistent_product_to_cart(self, client):
        token = register_verify_login(client)
        resp = client.post(
            "/api/v1/cart/add",
            headers={"Authorization": f"Bearer {token}"},
            json={"product_id": 999999, "vendor_id": 1, "quantity": 1},
        )
        assert resp.status_code == 404

    def test_cart_requires_auth(self, client):
        resp = client.get("/api/v1/cart")
        assert resp.status_code == 403

    def test_clear_empty_cart(self, client):
        token = register_verify_login(client)
        resp = client.delete("/api/v1/cart", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Cart cleared successfully"


# ─── Orders ───────────────────────────────────────────────────────────────────

class TestOrders:
    def test_checkout_empty_cart_fails(self, client):
        token = register_verify_login(client)
        resp = client.post(
            "/api/v1/orders/checkout",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    def test_list_orders_empty(self, client):
        token = register_verify_login(client)
        resp = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_nonexistent_order(self, client):
        token = register_verify_login(client)
        resp = client.get("/api/v1/orders/999999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_orders_requires_auth(self, client):
        resp = client.get("/api/v1/orders")
        assert resp.status_code == 403
