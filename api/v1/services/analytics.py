from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from api.v1.models.analytics_summary import AnalyticsSummary
from api.v1.models.order import Order
from api.v1.models.user import User
from api.v1.models.vendor import Vendor
from api.v1.models.marketplace import Marketplace


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def get_summary(self) -> AnalyticsSummary:
        total_users = self.db.query(User).count()
        active_users = self.db.query(User).filter(User.is_active.is_(True)).count()
        total_vendors = self.db.query(Vendor).count()
        active_vendors = self.db.query(Vendor).filter(Vendor.status == "activated").count()
        total_orders = self.db.query(Order).count()
        completed_orders = self.db.query(Order).filter(Order.status == "completed").count()
        total_revenue = self.db.query(Order).with_entities(Order.total_price).all()
        total_revenue_value = sum(float(value[0] or 0) for value in total_revenue)
        shopping_lists_created = self.db.query(Marketplace).count()

        return AnalyticsSummary(
            total_users=total_users,
            active_users=active_users,
            total_vendors=total_vendors,
            active_vendors=active_vendors,
            total_orders=total_orders,
            completed_orders=completed_orders,
            total_revenue=total_revenue_value,
            shopping_lists_created=shopping_lists_created,
        )
