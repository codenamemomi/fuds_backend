import enum
from datetime import time
from typing import Optional

from sqlalchemy import String, Time, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.v1.models.base_class import Base
from api.v1.models.categories import VendorCategory  # re-export for imports


class VendorStatus(str, enum.Enum):
    ACTIVATED = "activated"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


# Re-export so `from api.v1.models.vendor import VendorCategory` still works
__all__ = ["Vendor", "VendorStatus", "VendorCategory"]


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # String(40) supports package_delivery / local_market and future tags
    category: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
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
