from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.v1.models.product import Product, ProductCategory
from api.v1.models.vendor import Vendor, VendorCategory, VendorStatus
from api.v1.schema.product import ProductRead, ProductWithVendor
from api.v1.schema.vendor import VendorRead, VendorWithProducts


class BrowseService:
    def __init__(self, db: Session):
        self.db = db

    # ─── Vendor Browsing ─────────────────────────────────────────────────────

    def list_vendors(
        self,
        category: Optional[VendorCategory] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> list[VendorRead]:
        query = self.db.query(Vendor).filter(Vendor.status == VendorStatus.ACTIVATED)

        if category:
            query = query.filter(Vendor.category == category)
        if search:
            query = query.filter(Vendor.business_name.ilike(f"%{search}%"))

        offset = (page - 1) * limit
        vendors = query.offset(offset).limit(limit).all()
        return [VendorRead.model_validate(v) for v in vendors]

    def get_vendor_with_products(self, vendor_id: int) -> VendorWithProducts:
        vendor = (
            self.db.query(Vendor)
            .filter(Vendor.id == vendor_id, Vendor.status == VendorStatus.ACTIVATED)
            .first()
        )
        if not vendor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")

        product_reads = [ProductRead.model_validate(p) for p in vendor.products]
        vendor_data = VendorRead.model_validate(vendor).model_dump()
        return VendorWithProducts(**vendor_data, products=product_reads)

    # ─── Product Browsing ────────────────────────────────────────────────────

    def list_products(
        self,
        vendor_id: Optional[int] = None,
        category: Optional[ProductCategory] = None,
        name: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        page: int = 1,
        limit: int = 20,
    ) -> list[ProductRead]:
        query = self.db.query(Product)

        if vendor_id:
            query = query.filter(Product.vendor_id == vendor_id)
        if category:
            query = query.filter(Product.category == category)
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
