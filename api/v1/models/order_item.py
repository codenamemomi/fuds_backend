from sqlalchemy import ForeignKey, Numeric, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.v1.models.base_class import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    vendor: Mapped["Vendor"] = relationship(back_populates="order_items")
    product: Mapped["Product"] = relationship(back_populates="order_items")
