from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.v1.schema.category import BrowseCategoryRead
from api.v1.schema.product import ProductRead, ProductWithVendor
from api.v1.schema.vendor import VendorRead, VendorWithProducts
from api.v1.services.browse import BrowseService

router = APIRouter(prefix="/browse", tags=["browse"])


def get_browse_service(db: Session = Depends(get_db)) -> BrowseService:
    return BrowseService(db)


# ─── Categories (Home grid) ───────────────────────────────────────────────────

@router.get("/categories", response_model=list[BrowseCategoryRead])
def list_categories(service: BrowseService = Depends(get_browse_service)):
    """
    Consumer browse groups for the Home category grid.
    Pass a group's `key` as `?group=` on /browse/vendors or /browse/products.
    """
    return service.list_browse_categories()


# ─── Vendors ──────────────────────────────────────────────────────────────────

@router.get("/vendors", response_model=list[VendorRead])
def list_vendors(
    category: Optional[str] = Query(
        None,
        description="Fine-grained vendor category (restaurant, pharmacy, shop, …)",
    ),
    group: Optional[str] = Query(
        None,
        description="Browse group from /browse/categories (food, grocery, shops, pharmacy, packages)",
    ),
    search: Optional[str] = Query(None, description="Search vendor name"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    service: BrowseService = Depends(get_browse_service),
):
    """Browse active vendors. Prefer `group` for Home tiles; use `category` for exact type."""
    return service.list_vendors(
        category=category,
        group=group,
        search=search,
        page=page,
        limit=limit,
    )


@router.get("/vendors/{vendor_id}", response_model=VendorWithProducts)
def get_vendor_detail(
    vendor_id: int,
    service: BrowseService = Depends(get_browse_service),
):
    """Get a single vendor's details along with all its products."""
    return service.get_vendor_with_products(vendor_id)


# ─── Products ─────────────────────────────────────────────────────────────────

@router.get("/products", response_model=list[ProductRead])
def list_products(
    vendor_id: Optional[int] = Query(None, description="Filter by vendor"),
    category: Optional[str] = Query(None, description="Fine-grained product category"),
    group: Optional[str] = Query(None, description="Browse group: food, grocery, shops, …"),
    name: Optional[str] = Query(None, description="Search product name"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price (Naira)"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price (Naira)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    service: BrowseService = Depends(get_browse_service),
):
    """Browse products across all vendors with flexible filters."""
    return service.list_products(
        vendor_id=vendor_id,
        category=category,
        group=group,
        name=name,
        min_price=min_price,
        max_price=max_price,
        page=page,
        limit=limit,
    )


@router.get("/products/{product_id}", response_model=ProductWithVendor)
def get_product_detail(
    product_id: int,
    service: BrowseService = Depends(get_browse_service),
):
    """Get a single product's details including vendor context."""
    return service.get_product_detail(product_id)
