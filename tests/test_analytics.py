import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.db.session import get_db
from api.v1.models import Base, Order, Marketplace
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


class TestAnalytics:
    def test_analytics_summary_fields(self, client):
        """Verify that summary fields reflect the renamed and removed fields correctly."""
        # Insert a mock marketplace (grocery subscription) to verify lists due
        db = TestingSessionLocal()
        # Create a mock user first
        from api.v1.models.user import User
        user = User(
            fullname="Test User",
            email="test@example.com",
            phone="08033334444",
            password_hash="...",
            is_active=True,
            phone_verified=True,
        )
        db.add(user)
        db.commit()

        sub = Marketplace(
            user_id=user.id,
            item_list=["Tomatoes", "Onions"],
            frequency="weekly",
            status="active",
        )
        db.add(sub)
        db.commit()

        # Fetch the analytics summary
        resp = client.get("/api/v1/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()

        # Check renamed/modified fields
        assert "revenue" in data
        assert "shopping_lists_due" in data
        assert isinstance(data["shopping_lists_due"], list)
        assert len(data["shopping_lists_due"]) == 1
        assert data["shopping_lists_due"][0]["item_list"] == ["Tomatoes", "Onions"]

        # Check removed fields are not present
        assert "total_revenue" not in data
        assert "completed_orders" not in data
        assert "subscriptions_due_this_week" not in data

        db.close()

    def test_analytics_export_csv(self, client):
        """Verify that the CSV export endpoint functions and returns correct headers."""
        db = TestingSessionLocal()
        # Add a mock order
        order = Order(
            user_id=1,
            status="completed",
            total_price=5000.0,
        )
        db.add(order)
        db.commit()

        resp = client.get("/api/v1/analytics/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment; filename=" in resp.headers["content-disposition"]
        
        content = resp.text
        lines = content.strip().split("\r\n")
        assert len(lines) >= 2
        
        # Verify headers
        headers = lines[0].split(",")
        assert headers == ["Order ID", "Date", "Status", "Revenue", "Vendor", "Customer"]
        
        # Verify row values
        row = lines[1].split(",")
        assert row[2] == "completed"
        assert float(row[3]) == 5000.0

        db.close()
