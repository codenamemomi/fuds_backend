from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.v1.models.product import ProductCategory
from api.v1.models.vendor import VendorCategory
from api.v1.schema.product import ProductRead, ProductWithVendor
from api.v1.schema.vendor import VendorRead, VendorWithProducts
from api.v1.services.browse import BrowseService

router = APIRouter(prefix="/browse", tags=["browse"])


def get_browse_service(db: Session = Depends(get_db)) -> BrowseService:
    return BrowseService(db)


# ─── Vendors ──────────────────────────────────────────────────────────────────

@router.get("/vendors", response_model=list[VendorRead])
def list_vendors(
    category: Optional[VendorCategory] = Query(None, description="Filter by vendor category"),
    search: Optional[str] = Query(None, description="Search vendor name"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    service: BrowseService = Depends(get_browse_service),
):
    """Browse all active vendors. Optionally filter by category or search by name."""
    return service.list_vendors(category=category, search=search, page=page, limit=limit)


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
    category: Optional[ProductCategory] = Query(None, description="Filter by product category"),
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
