from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    vendor_id: int
    name: str = Field(..., min_length=2)
    price: float = Field(..., gt=0)
    category: Optional[str] = None
    image_url: Optional[str] = None


class ProductRead(ProductCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)
