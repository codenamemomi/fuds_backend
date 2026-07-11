from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreate(BaseModel):
    vendor_id: int
    product_id: int
    quantity: int = Field(default=1, ge=1)
    price: float = Field(..., ge=0)


class OrderCreate(BaseModel):
    user_id: int
    status: str = "pending"
    delivery_time: Optional[datetime] = None
    rider_name: Optional[str] = None
    rider_phone: Optional[str] = None
    payment_status: str = "pending"
    total_price: float = 0.0
    parent_order_id: Optional[int] = None
    vendor_id: Optional[int] = None
    items: list[OrderItemCreate] = []


class CheckoutRequest(BaseModel):
    delivery_time: Optional[datetime] = None


class OrderItemRead(BaseModel):
    id: int
    product_id: int
    vendor_id: int
    quantity: int
    price: float
    product_name: Optional[str] = None
    vendor_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OrderRead(BaseModel):
    id: int
    user_id: int
    parent_order_id: Optional[int] = None
    vendor_id: Optional[int] = None
    status: str
    delivery_time: Optional[datetime] = None
    payment_status: str
    total_price: float
    created_at: datetime
    completed_at: Optional[datetime] = None
    items: list[OrderItemRead] = []

    model_config = ConfigDict(from_attributes=True)

