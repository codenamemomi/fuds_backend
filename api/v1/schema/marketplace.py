from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from api.v1.models.marketplace import MarketplaceFrequency


class MarketplaceProductRead(BaseModel):
    id: int
    name: str
    price: float
    category: Optional[str] = None
    aisle: Optional[str] = None
    image_url: Optional[str] = None


class MarketplaceProductCreate(BaseModel):
    name: str = Field(..., min_length=2)
    price: float = Field(..., gt=0)
    category: Optional[str] = None
    aisle: Optional[str] = None
    image_url: Optional[str] = None


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
    marketplace_product_id: Optional[int] = None


class GroceryChangeRead(BaseModel):
    product_id: int
    name: str
    quantity: int
    amount: float


class GroceryAisleRead(BaseModel):
    key: str
    label: str
    subtitle: str
    icon: str
    product_count: int = 0


class GroceryCatalogRead(BaseModel):
    aisles: list[GroceryAisleRead]
    products: list[MarketplaceProductRead]


class GrocerySubscriptionCreate(BaseModel):
    items: list[GroceryItemIn] = Field(..., min_length=1)
    frequency: MarketplaceFrequency = MarketplaceFrequency.WEEKLY
    next_delivery: Optional[date] = None


class GrocerySubscriptionUpdate(BaseModel):
    items: Optional[list[GroceryItemIn]] = None
    frequency: Optional[MarketplaceFrequency] = None
    next_delivery: Optional[date] = None
    status: Optional[str] = None


class GrocerySubscriptionCheckout(BaseModel):
    cycles: int = Field(default=1, ge=1, le=5)


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
    payment_status: Optional[str] = None
    added_items: list[GroceryChangeRead] = []
    removed_items: list[GroceryChangeRead] = []
    change_total: float = 0.0

    model_config = ConfigDict(from_attributes=True)


MarketplaceCreate = GrocerySubscriptionCreate
MarketplaceRead = GrocerySubscriptionRead
