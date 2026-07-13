"""Pydantic schemas for Paystack payments (card + Titan bank transfer)."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InitializePaymentRequest(BaseModel):
    """
    Start a Paystack hosted charge for a parent order created at checkout.

    `order_id` must be a top-level (parent) order belonging to the caller.
    """

    order_id: int = Field(..., ge=1)
    callback_url: Optional[str] = Field(
        default=None,
        description="Where Paystack redirects the user after payment. Falls back to settings.",
    )


class InitializePaymentResponse(BaseModel):
    payment_id: int
    order_id: int
    reference: str
    access_code: str
    authorization_url: str
    amount: float
    amount_kobo: int
    currency: str
    status: str
    payment_method: str = "card"


class InitializeTransferRequest(BaseModel):
    """
    Start a pay-with-transfer payment via Paystack Titan dedicated virtual account.

    Client shows account_number / bank_name / amount; customer transfers from any bank.
    """

    order_id: int = Field(..., ge=1)


class TransferAccountDetails(BaseModel):
    account_number: str
    account_name: str
    bank_name: str
    bank_slug: Optional[str] = None


class InitializeTransferResponse(BaseModel):
    payment_id: int
    order_id: int
    reference: str
    amount: float
    amount_kobo: int
    currency: str
    status: str
    payment_method: str = "bank_transfer"
    channel: str = "dedicated_nuban"
    # What the customer should transfer to
    account: TransferAccountDetails
    instructions: str
    # Optional: when the payment intent should be treated as expired client-side
    expires_hint: Optional[str] = None


class VerifyPaymentRequest(BaseModel):
    """Optional body when verifying by reference via POST."""

    reference: str = Field(..., min_length=6, max_length=100)


class PaymentRead(BaseModel):
    id: int
    user_id: int
    order_id: int
    amount: float
    amount_kobo: int
    currency: str
    provider: str
    payment_method: str = "card"
    reference: str
    access_code: Optional[str] = None
    authorization_url: Optional[str] = None
    account_number: Optional[str] = None
    account_name: Optional[str] = None
    bank_name: Optional[str] = None
    bank_slug: Optional[str] = None
    account_expires_at: Optional[datetime] = None
    status: str
    provider_status: Optional[str] = None
    channel: Optional[str] = None
    gateway_response: Optional[str] = None
    provider_transaction_id: Optional[str] = None
    paystack_customer_code: Optional[str] = None
    paid_at: Optional[datetime] = None
    metadata_json: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_amount(cls, v: Any) -> float:
        return float(v) if v is not None else 0.0


class VerifyPaymentResponse(BaseModel):
    payment: PaymentRead
    order_payment_status: str
    message: str


class WebhookAck(BaseModel):
    status: str = "ok"
    message: str = "received"
