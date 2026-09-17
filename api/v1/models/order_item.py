from typing import Optional

from sqlalchemy import ForeignKey, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.v1.models.base_class import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    marketplace_product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("marketplace_products.id"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    vendor: Mapped["Vendor"] = relationship(back_populates="order_items")
    product: Mapped["Product"] = relationship(back_populates="order_items")
    marketplace_product: Mapped[Optional["MarketplaceProduct"]] = relationship()
