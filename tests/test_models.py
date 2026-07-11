from api.v1.models import (
    Base,
    GrocerySubscription,
    Marketplace,
    MarketplaceFrequency,
    MealType,
    Order,
    OrderItem,
    Product,
    ProductCategory,
    ScheduledMeal,
    User,
    Vendor,
    VendorCategory,
)
from api.v1.models.vendor import VendorStatus


def test_model_imports():
    assert Base is not None
    assert User.__tablename__ == "users"
    assert Vendor.__tablename__ == "vendors"
    assert Product.__tablename__ == "products"
    assert Order.__tablename__ == "orders"
    assert OrderItem.__tablename__ == "order_items"
    assert ScheduledMeal.__tablename__ == "scheduled_meals"
    assert GrocerySubscription.__tablename__ == "grocery_subscriptions"
    assert Marketplace is GrocerySubscription


def test_vendor_status_values():
    assert VendorStatus.ACTIVATED.value == "activated"
    assert VendorStatus.SUSPENDED.value == "suspended"
    assert VendorStatus.DEACTIVATED.value == "deactivated"


def test_marketplace_frequency_values():
    assert MarketplaceFrequency.WEEKLY.value == "weekly"
    assert MarketplaceFrequency.BI_WEEKLY.value == "bi-weekly"
    assert MarketplaceFrequency.MONTHLY.value == "monthly"


def test_category_enums_have_expected_values():
    assert VendorCategory.RESTAURANT.value == "restaurant"
    assert VendorCategory.GROCERY_STORE.value == "grocery_store"
    assert VendorCategory.SUPERMARKET.value == "supermarket"
    assert VendorCategory.BAKERY.value == "bakery"
    assert VendorCategory.PHARMACY.value == "pharmacy"
    assert ProductCategory.RESTAURANT.value == "restaurant"


def test_meal_type_values():
    assert MealType.BREAKFAST.value == "breakfast"
    assert MealType.LUNCH.value == "lunch"
    assert MealType.DINNER.value == "dinner"


def test_order_can_represent_multi_vendor_checkout():
    assert Order.__tablename__ == "orders"
    assert "parent_order_id" in Order.__table__.c
    assert "vendor_id" in Order.__table__.c
    assert "rider_name" in Order.__table__.c
    assert "rider_phone" in Order.__table__.c


def test_user_has_otp_verification_fields():
    assert "otp_expires_at" not in User.__table__.c
    assert "otp" not in User.__table__.c
    assert "phone_verified" in User.__table__.c
