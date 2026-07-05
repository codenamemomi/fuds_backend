"""Schema package for API v1."""

from api.v1.schema.analytics import AnalyticsSummaryRead
from api.v1.schema.marketplace import MarketplaceCreate, MarketplaceRead
from api.v1.schema.order import OrderCreate, OrderItemCreate, OrderRead
from api.v1.schema.product import ProductCreate, ProductRead
from api.v1.schema.scheduled_meal import ScheduledMealCreate, ScheduledMealRead
from api.v1.schema.user import UserCreate, UserRead
from api.v1.schema.vendor import VendorCreate, VendorRead

__all__ = [
    "UserCreate",
    "UserRead",
    "VendorCreate",
    "VendorRead",
    "ProductCreate",
    "ProductRead",
    "OrderItemCreate",
    "OrderCreate",
    "OrderRead",
    "MarketplaceCreate",
    "MarketplaceRead",
    "ScheduledMealCreate",
    "ScheduledMealRead",
    "AnalyticsSummaryRead",
]
