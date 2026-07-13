from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.v1.models.categories import ProductCategory


class ProductCreate(BaseModel):
    vendor_id: int
    name: str = Field(..., min_length=2)
    price: float = Field(..., gt=0)
    category: Optional[str] = None
    image_url: Optional[str] = None

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v):
        if v is None:
            return v
        if isinstance(v, ProductCategory):
            return v.value
        value = str(v).strip().lower().replace(" ", "_").replace("-", "_")
        try:
            return ProductCategory(value).value
        except ValueError as exc:
            allowed = ", ".join(c.value for c in ProductCategory)
            raise ValueError(f"Invalid product category. Allowed: {allowed}") from exc


class ProductRead(ProductCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ProductWithVendor(ProductRead):
    """Product detail with minimal vendor context."""

    vendor_name: Optional[str] = None
    vendor_category: Optional[str] = None
    vendor_address: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
