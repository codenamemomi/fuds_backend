import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.v1.models.base_class import Base


class MarketplaceFrequency(str, enum.Enum):
    WEEKLY = "weekly"
    BI_WEEKLY = "bi-weekly"
    MONTHLY = "monthly"


class GrocerySubscription(Base):
    __tablename__ = "grocery_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_list: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    frequency: Mapped[MarketplaceFrequency] = mapped_column(String(20), nullable=False)
    next_delivery: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="grocery_subscriptions")


Marketplace = GrocerySubscription
