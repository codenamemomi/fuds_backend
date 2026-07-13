"""Schemas for consumer-facing browse categories / groups."""

from typing import Optional

from pydantic import BaseModel, Field


class BrowseCategoryRead(BaseModel):
    """One tile on the Home category grid (Food, Grocery, …)."""

    key: str = Field(..., description="Browse group key, e.g. food, grocery")
    label: str
    subtitle: str
    icon: str = Field(..., description="Icon key for the mobile client")
    vendor_categories: list[str] = Field(
        ...,
        description="Underlying VendorCategory values this group includes",
    )
    vendor_count: int = 0


class VendorCategoryMeta(BaseModel):
    value: str
    label: str
    group: Optional[str] = None
