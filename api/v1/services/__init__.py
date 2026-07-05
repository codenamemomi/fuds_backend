"""Service package for API v1."""

from api.v1.services.analytics import AnalyticsService
from api.v1.services.base import BaseService
from api.v1.services.marketplace import MarketplaceService
from api.v1.services.order import OrderService
from api.v1.services.product import ProductService
from api.v1.services.scheduled_meal import ScheduledMealService
from api.v1.services.user import UserService
from api.v1.services.vendor import VendorService

__all__ = [
    "BaseService",
    "UserService",
    "VendorService",
    "ProductService",
    "OrderService",
    "MarketplaceService",
    "ScheduledMealService",
    "AnalyticsService",
]
