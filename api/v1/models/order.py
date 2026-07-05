from datetime import datetime, time
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.v1.models.base_class import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    parent_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), nullable=True)
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    delivery_time: Mapped[Optional[time]] = mapped_column(nullable=True)
    payment_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="orders")
    vendor: Mapped[Optional["Vendor"]] = relationship()
    parent_order: Mapped[Optional["Order"]] = relationship(remote_side="Order.id", back_populates="sub_orders")
    sub_orders: Mapped[list["Order"]] = relationship(back_populates="parent_order", cascade="all, delete-orphan")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
