from datetime import time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.v1.models.categories import VendorCategory
from api.v1.models.vendor import VendorStatus


class VendorCreate(BaseModel):
    business_name: str = Field(..., min_length=2)
    category: Optional[str] = None
    business_description: Optional[str] = None
    business_logo: Optional[str] = None
    cac: Optional[str] = None
    rc_number: Optional[str] = None
    address: Optional[str] = None
    tin: Optional[str] = None
    opening_time: Optional[time] = None
    closing_time: Optional[time] = None
    status: VendorStatus = VendorStatus.ACTIVATED

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v):
        if v is None:
            return v
        if isinstance(v, VendorCategory):
            return v.value
        value = str(v).strip().lower().replace(" ", "_").replace("-", "_")
        try:
            return VendorCategory(value).value
        except ValueError as exc:
            allowed = ", ".join(c.value for c in VendorCategory)
            raise ValueError(f"Invalid vendor category. Allowed: {allowed}") from exc


class VendorRead(VendorCreate):
    id: int
    # Set by BrowseService from taxonomy (food / grocery / shops / …)
    browse_group: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class VendorWithProducts(VendorRead):
    """Vendor detail response including its product list."""

    products: list["ProductRead"] = []


from api.v1.schema.product import ProductRead  # noqa: E402 — avoid circular import

VendorWithProducts.model_rebuild()
