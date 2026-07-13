"""
Shared browse taxonomy for FUDS.

`VendorCategory` / `ProductCategory` are fine-grained store types stored in DB.
`BrowseGroup` is the consumer-facing bucket (Food, Grocery, Shops, …) used by the
mobile home grid — one group may map to several vendor categories.
"""

from __future__ import annotations

import enum
from typing import TypedDict


class VendorCategory(str, enum.Enum):
    RESTAURANT = "restaurant"
    GROCERY_STORE = "grocery_store"
    SUPERMARKET = "supermarket"
    BAKERY = "bakery"
    PHARMACY = "pharmacy"
    SHOP = "shop"  # retail / convenience / fashion
    LOCAL_MARKET = "local_market"  # open-air / traditional markets
    PACKAGE_DELIVERY = "package_delivery"  # courier / send packages


# Keep product categories aligned with vendor types for filtering
ProductCategory = VendorCategory


class BrowseGroup(str, enum.Enum):
    """UI category chips on Home (Glovo / Chowdeck style)."""

    FOOD = "food"
    GROCERY = "grocery"
    SHOPS = "shops"
    PHARMACY = "pharmacy"
    PACKAGES = "packages"


class BrowseGroupMeta(TypedDict):
    key: str
    label: str
    subtitle: str
    icon: str
    vendor_categories: list[str]


# Single source of truth for frontend + backend filtering
BROWSE_GROUPS: list[BrowseGroupMeta] = [
    {
        "key": BrowseGroup.FOOD.value,
        "label": "Food",
        "subtitle": "Hot meals & bakeries",
        "icon": "food",
        "vendor_categories": [
            VendorCategory.RESTAURANT.value,
            VendorCategory.BAKERY.value,
        ],
    },
    {
        "key": BrowseGroup.GROCERY.value,
        "label": "Grocery",
        "subtitle": "Fresh & pantry",
        "icon": "grocery",
        "vendor_categories": [
            VendorCategory.GROCERY_STORE.value,
            VendorCategory.SUPERMARKET.value,
            VendorCategory.LOCAL_MARKET.value,
        ],
    },
    {
        "key": BrowseGroup.SHOPS.value,
        "label": "Shops",
        "subtitle": "Retail & essentials",
        "icon": "shops",
        "vendor_categories": [VendorCategory.SHOP.value],
    },
    {
        "key": BrowseGroup.PHARMACY.value,
        "label": "Pharmacy",
        "subtitle": "Health & beauty",
        "icon": "pharmacy",
        "vendor_categories": [VendorCategory.PHARMACY.value],
    },
    {
        "key": BrowseGroup.PACKAGES.value,
        "label": "Packages",
        "subtitle": "Send anything",
        "icon": "packages",
        "vendor_categories": [VendorCategory.PACKAGE_DELIVERY.value],
    },
]


def vendor_categories_for_group(group: str | BrowseGroup) -> list[str]:
    key = group.value if isinstance(group, BrowseGroup) else group
    for g in BROWSE_GROUPS:
        if g["key"] == key:
            return list(g["vendor_categories"])
    return []


def group_for_vendor_category(category: str | VendorCategory | None) -> str | None:
    if category is None:
        return None
    value = category.value if isinstance(category, VendorCategory) else category
    for g in BROWSE_GROUPS:
        if value in g["vendor_categories"]:
            return g["key"]
    return None
