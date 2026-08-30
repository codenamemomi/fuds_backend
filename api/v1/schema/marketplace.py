from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from api.v1.models.marketplace import MarketplaceFrequency
from api.v1.schema.product import ProductWithVendor


class GroceryItemIn(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=50)


class GroceryItemRead(BaseModel):
    product_id: int
    quantity: int
    name: str
    price: float
    subtotal: float
    aisle: Optional[str] = None
    image_url: Optional[str] = None
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None


class GroceryAisleRead(BaseModel):
    key: str
    label: str
    subtitle: str
    icon: str
    product_count: int = 0


class GroceryCatalogRead(BaseModel):
    aisles: list[GroceryAisleRead]
    products: list[ProductWithVendor]


class GrocerySubscriptionCreate(BaseModel):
    items: list[GroceryItemIn] = Field(..., min_length=1)
    frequency: MarketplaceFrequency = MarketplaceFrequency.WEEKLY
    next_delivery: Optional[date] = None


class GrocerySubscriptionUpdate(BaseModel):
    items: Optional[list[GroceryItemIn]] = None
    frequency: Optional[MarketplaceFrequency] = None
    next_delivery: Optional[date] = None
    status: Optional[str] = None


class GrocerySubscriptionRead(BaseModel):
    id: int
    user_id: int
    frequency: MarketplaceFrequency
    next_delivery: Optional[datetime] = None
    status: str
    order_id: Optional[int] = None
    created_at: datetime
    items: list[GroceryItemRead] = []
    item_count: int = 0
    total: float = 0.0

    model_config = ConfigDict(from_attributes=True)


MarketplaceCreate = GrocerySubscriptionCreate
MarketplaceRead = GrocerySubscriptionRead
