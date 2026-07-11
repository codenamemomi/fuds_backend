import enum
from datetime import time
from typing import Optional

from sqlalchemy import String, Time, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.v1.models.base_class import Base


class VendorStatus(str, enum.Enum):
    ACTIVATED = "activated"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class VendorCategory(str, enum.Enum):
    RESTAURANT = "restaurant"
    GROCERY_STORE = "grocery_store"
    SUPERMARKET = "supermarket"
    BAKERY = "bakery"
    PHARMACY = "pharmacy"


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[VendorCategory]] = mapped_column(String(20), nullable=True)
    business_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_logo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cac: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rc_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tin: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    opening_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    closing_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    status: Mapped[VendorStatus] = mapped_column(String(20), default=VendorStatus.ACTIVATED, nullable=False)

    products: Mapped[list["Product"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
    scheduled_meals: Mapped[list["ScheduledMeal"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
