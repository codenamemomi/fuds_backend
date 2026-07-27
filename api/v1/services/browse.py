import json
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.utils.redis_utils import redis_client
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
        Checks Redis cache first.
        """
        cache_key = "cache:browse:categories"
        try:
            cached = redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                return [BrowseCategoryRead(**d) for d in data]
        except Exception:
            pass

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

        try:
            redis_client.setex(cache_key, 3600, json.dumps([c.model_dump() for c in result]))
        except Exception:
            pass

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
        """
        Browse active vendors. Checks Redis cache first.
        """
        cache_key = f"cache:browse:vendors:list:category={category}:group={group}:search={search}:page={page}:limit={limit}"
        try:
            cached = redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                return [VendorRead(**d) for d in data]
        except Exception:
            pass

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
        result = [self._vendor_read(v) for v in vendors]

        try:
            redis_client.setex(cache_key, 3600, json.dumps([v.model_dump() for v in result]))
        except Exception:
            pass

        return result

    def get_vendor_with_products(self, vendor_id: int) -> VendorWithProducts:
        """
        Get vendor details with all products. Checks Redis cache first.
        """
        cache_key = f"cache:browse:vendors:detail:{vendor_id}"
        try:
            cached = redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                return VendorWithProducts(**data)
        except Exception:
            pass

        vendor = (
            self.db.query(Vendor)
            .filter(Vendor.id == vendor_id, Vendor.status == VendorStatus.ACTIVATED)
            .first()
        )
        if not vendor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")

        product_reads = [ProductRead.model_validate(p) for p in vendor.products]
        base = self._vendor_read(vendor).model_dump()
        result = VendorWithProducts(**base, products=product_reads)

        try:
            redis_client.setex(cache_key, 3600, result.model_dump_json())
        except Exception:
            pass

        return result

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
    ) -> list[ProductWithVendor]:
        """
        Browse / search products. Checks Redis cache first.
        """
        cache_key = f"cache:browse:products:list:vendor_id={vendor_id}:category={category}:group={group}:name={name}:min_price={min_price}:max_price={max_price}:page={page}:limit={limit}"
        try:
            cached = redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                return [ProductWithVendor(**d) for d in data]
        except Exception:
            pass

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
            term = name.strip()
            if term:
                query = query.filter(Product.name.ilike(f"%{term}%"))
        if min_price is not None:
            query = query.filter(Product.price >= min_price)
        if max_price is not None:
            query = query.filter(Product.price <= max_price)

        offset = (page - 1) * limit
        products = (
            query.order_by(Product.name.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        result = [self._product_with_vendor(p) for p in products]

        try:
            redis_client.setex(cache_key, 3600, json.dumps([p.model_dump() for p in result]))
        except Exception:
            pass

        return result

    def get_product_detail(self, product_id: int) -> ProductWithVendor:
        """
        Get product details. Checks Redis cache first.
        """
        cache_key = f"cache:browse:products:detail:{product_id}"
        try:
            cached = redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                return ProductWithVendor(**data)
        except Exception:
            pass

        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        result = self._product_with_vendor(product)

        try:
            redis_client.setex(cache_key, 3600, result.model_dump_json())
        except Exception:
            pass

        return result

    # ─── Cache Pre-warming ───────────────────────────────────────────────────

    def warm_cache(self):
        """
        Pre-queries and caches categories, default lists, group filter lists,
        active vendor details, and product details in Redis.
        """
        import logging
        logger = logging.getLogger("cache_warmer")
        logger.info("Initializing Redis database cache pre-warming...")
        
        try:
            # 1. Warm Categories
            cats = self.list_browse_categories()
            logger.info(f"Warmed {len(cats)} browse categories.")

            # 2. Warm Default lists (limit=40 for vendors, limit=12 for products)
            default_vendors = self.list_vendors(limit=40)
            logger.info(f"Warmed default active vendors list (count: {len(default_vendors)}).")

            default_products = self.list_products(limit=12)
            logger.info(f"Warmed default active products list (count: {len(default_products)}).")

            # 3. Warm Group lists
            for g in BROWSE_GROUPS:
                group_key = g["key"]
                group_vendors = self.list_vendors(group=group_key, limit=40)
                group_products = self.list_products(group=group_key, limit=12)
                logger.info(
                    f"Warmed group '{group_key}' lists: "
                    f"{len(group_vendors)} vendors, {len(group_products)} products."
                )

            # 4. Warm active Vendor details
            vendors = self.db.query(Vendor).filter(Vendor.status == VendorStatus.ACTIVATED).all()
            for v in vendors:
                self.get_vendor_with_products(v.id)
            logger.info(f"Warmed details for {len(vendors)} active vendors.")

            # 5. Warm Product details
            products = self.db.query(Product).all()
            for p in products:
                self.get_product_detail(p.id)
            logger.info(f"Warmed details for {len(products)} products.")

            logger.info("Redis database cache pre-warming successfully completed!")
        except Exception as e:
            logger.error(f"Error during cache pre-warming: {e}", exc_info=True)

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _product_with_vendor(self, product: Product) -> ProductWithVendor:
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
