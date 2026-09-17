import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.v1.models.base_class import Base


class MarketplaceFrequency(str, enum.Enum):
    WEEKLY = "weekly"
    BI_WEEKLY = "bi-weekly"
    MONTHLY = "monthly"


class MarketplaceProduct(Base):
    __tablename__ = "marketplace_products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    aisle: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False, index=True)


class GrocerySubscription(Base):
    __tablename__ = "grocery_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_list: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    items: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    change_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    frequency: Mapped[MarketplaceFrequency] = mapped_column(String(20), nullable=False)
    next_delivery: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="grocery_subscriptions")


Marketplace = GrocerySubscription
