from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.v1.models.categories import (
    BROWSE_GROUPS,
    BrowseGroup,
    ProductCategory,
    VendorCategory,
    group_for_vendor_category,
    vendor_categories_for_group,
)
from api.v1.models.product import Product
from api.v1.models.vendor import Vendor, VendorStatus
from api.v1.schema.category import BrowseCategoryRead
from api.v1.schema.product import ProductRead, ProductWithVendor
from api.v1.schema.vendor import VendorRead, VendorWithProducts


class BrowseService:
    def __init__(self, db: Session):
        self.db = db

    # ─── Categories (Home grid) ───────────────────────────────────────────────

    def list_browse_categories(self) -> list[BrowseCategoryRead]:
        """
        Consumer-facing category tiles with live vendor counts.
        Frontend should use `key` as the `group` query param on /browse/vendors.
        """
        # Count activated vendors per fine-grained category
        rows = (
            self.db.query(Vendor.category, func.count(Vendor.id))
            .filter(Vendor.status == VendorStatus.ACTIVATED)
            .group_by(Vendor.category)
            .all()
        )
        counts: dict[str, int] = {}
        for cat, n in rows:
            if cat:
                counts[str(cat)] = int(n)

        result: list[BrowseCategoryRead] = []
        for g in BROWSE_GROUPS:
            total = sum(counts.get(vc, 0) for vc in g["vendor_categories"])
            result.append(
                BrowseCategoryRead(
                    key=g["key"],
                    label=g["label"],
                    subtitle=g["subtitle"],
                    icon=g["icon"],
                    vendor_categories=list(g["vendor_categories"]),
                    vendor_count=total,
                )
            )
        return result

    # ─── Vendor Browsing ─────────────────────────────────────────────────────

    def list_vendors(
        self,
        category: Optional[str] = None,
        group: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> list[VendorRead]:
        query = self.db.query(Vendor).filter(Vendor.status == VendorStatus.ACTIVATED)

        # Prefer group (UI tile) over single category when both sent
        if group:
            cats = vendor_categories_for_group(group)
            if not cats:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown browse group '{group}'. "
                    f"Allowed: {', '.join(g['key'] for g in BROWSE_GROUPS)}",
                )
            query = query.filter(Vendor.category.in_(cats))
        elif category:
            try:
                cat_value = VendorCategory(category).value if not isinstance(category, VendorCategory) else category.value
            except ValueError as exc:
                allowed = ", ".join(c.value for c in VendorCategory)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid category. Allowed: {allowed}",
                ) from exc
            query = query.filter(Vendor.category == cat_value)

        if search:
            query = query.filter(Vendor.business_name.ilike(f"%{search}%"))

        offset = (page - 1) * limit
        vendors = query.order_by(Vendor.business_name.asc()).offset(offset).limit(limit).all()
        return [self._vendor_read(v) for v in vendors]

    def get_vendor_with_products(self, vendor_id: int) -> VendorWithProducts:
        vendor = (
            self.db.query(Vendor)
            .filter(Vendor.id == vendor_id, Vendor.status == VendorStatus.ACTIVATED)
            .first()
        )
        if not vendor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")

        product_reads = [ProductRead.model_validate(p) for p in vendor.products]
        base = self._vendor_read(vendor).model_dump()
        return VendorWithProducts(**base, products=product_reads)

    # ─── Product Browsing ────────────────────────────────────────────────────

    def list_products(
        self,
        vendor_id: Optional[int] = None,
        category: Optional[str] = None,
        group: Optional[str] = None,
        name: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        page: int = 1,
        limit: int = 20,
    ) -> list[ProductRead]:
        query = self.db.query(Product)

        if vendor_id:
            query = query.filter(Product.vendor_id == vendor_id)

        if group:
            cats = vendor_categories_for_group(group)
            if not cats:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown browse group '{group}'",
                )
            query = query.filter(Product.category.in_(cats))
        elif category:
            try:
                cat_value = (
                    ProductCategory(category).value
                    if not isinstance(category, ProductCategory)
                    else category.value
                )
            except ValueError as exc:
                allowed = ", ".join(c.value for c in ProductCategory)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid product category. Allowed: {allowed}",
                ) from exc
            query = query.filter(Product.category == cat_value)

        if name:
            query = query.filter(Product.name.ilike(f"%{name}%"))
        if min_price is not None:
            query = query.filter(Product.price >= min_price)
        if max_price is not None:
            query = query.filter(Product.price <= max_price)

        offset = (page - 1) * limit
        products = query.offset(offset).limit(limit).all()
        return [ProductRead.model_validate(p) for p in products]

    def get_product_detail(self, product_id: int) -> ProductWithVendor:
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        vendor = product.vendor
        data = ProductRead.model_validate(product).model_dump()
        return ProductWithVendor(
            **data,
            vendor_name=vendor.business_name if vendor else None,
            vendor_category=vendor.category if vendor else None,
            vendor_address=vendor.address if vendor else None,
        )

    def _vendor_read(self, vendor: Vendor) -> VendorRead:
        read = VendorRead.model_validate(vendor)
        read.browse_group = group_for_vendor_category(vendor.category)
        return read
