from datetime import time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from api.v1.models.vendor import VendorCategory, VendorStatus


class VendorCreate(BaseModel):
    business_name: str = Field(..., min_length=2)
    category: Optional[VendorCategory] = None
    business_description: Optional[str] = None
    business_logo: Optional[str] = None
    cac: Optional[str] = None
    rc_number: Optional[str] = None
    address: Optional[str] = None
    tin: Optional[str] = None
    opening_time: Optional[time] = None
    closing_time: Optional[time] = None
    status: VendorStatus = VendorStatus.ACTIVATED


class VendorRead(VendorCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class VendorWithProducts(VendorRead):
    """Vendor detail response including its product list."""
    products: list["ProductRead"] = []


from api.v1.schema.product import ProductRead  # noqa: E402 — avoid circular import
VendorWithProducts.model_rebuild()

