from typing import Optional

from pydantic import BaseModel, Field


class CartItemCreate(BaseModel):
    product_id: Optional[int] = None
    marketplace_product_id: Optional[int] = None
    vendor_id: Optional[int] = None
    quantity: int = Field(default=1, ge=1)


class CartItemUpdate(BaseModel):
    product_id: Optional[int] = None
    marketplace_product_id: Optional[int] = None
    quantity: int = Field(ge=0)


class CartItemRead(BaseModel):
    product_id: Optional[int] = None
    marketplace_product_id: Optional[int] = None
    vendor_id: Optional[int] = None
    name: str
    price: float
    quantity: int
    subtotal: float
    image_url: Optional[str] = None


class CartRead(BaseModel):
    user_id: int
    items: list[CartItemRead] = []
    total: float = 0.0
    item_count: int = 0
