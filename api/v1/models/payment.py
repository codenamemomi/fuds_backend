"""Payment model for Paystack (and future gateways)."""

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.v1.models.base_class import Base


class PaymentStatus(str, enum.Enum):
    """Internal payment lifecycle status."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    ABANDONED = "abandoned"


class PaymentProvider(str, enum.Enum):
    PAYSTACK = "paystack"


class PaymentMethod(str, enum.Enum):
    """How the customer is expected to pay."""

    CARD = "card"  # hosted checkout / authorization_url
    BANK_TRANSFER = "bank_transfer"  # Initialize Transaction with channels=["bank_transfer"]


class Payment(Base):
    """
    One payment attempt against a parent order.

    Amounts are stored in Naira on `amount` and kobo on `amount_kobo`
    (Paystack requires the smallest currency unit).

    bank_transfer uses standard Pay with Transfer (hosted checkout); temporary
    account is shown by Paystack. account_* fields are optional leftovers.
    """

    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("reference", name="uq_payments_reference"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)

    # Money
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)  # Naira
    amount_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="NGN", nullable=False)

    # Gateway identity
    provider: Mapped[str] = mapped_column(String(30), default=PaymentProvider.PAYSTACK.value, nullable=False)
    payment_method: Mapped[str] = mapped_column(
        String(30), default=PaymentMethod.CARD.value, nullable=False, index=True
    )
    reference: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    access_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    authorization_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Optional transfer account snapshot (not used for standard Pay with Transfer)
    account_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    account_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_slug: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    account_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(30), default=PaymentStatus.PENDING.value, nullable=False, index=True)
    provider_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g. success, failed, abandoned
    channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # card, bank_transfer
    gateway_response: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Paystack / gateway IDs
    provider_transaction_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    paystack_customer_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    raw_response: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="payments")
    order: Mapped["Order"] = relationship(back_populates="payments")
