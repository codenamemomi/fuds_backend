from datetime import datetime, time
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
    delivery_time: Optional[time] = None
    payment_status: str = "pending"
    total_price: float = 0.0
    parent_order_id: Optional[int] = None
    vendor_id: Optional[int] = None
    items: list[OrderItemCreate] = []


class OrderRead(OrderCreate):
    id: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
