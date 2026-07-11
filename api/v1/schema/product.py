from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from api.v1.models.product import ProductCategory


class ProductCreate(BaseModel):
    vendor_id: int
    name: str = Field(..., min_length=2)
    price: float = Field(..., gt=0)
    category: Optional[ProductCategory] = None
    image_url: Optional[str] = None


class ProductRead(ProductCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ProductWithVendor(ProductRead):
    """Product detail with minimal vendor context."""
    vendor_name: Optional[str] = None
    vendor_category: Optional[str] = None
    vendor_address: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

