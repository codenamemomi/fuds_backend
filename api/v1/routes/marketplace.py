from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.v1.models.user import User
from api.v1.schema.marketplace import (
    GroceryAisleRead,
    GroceryCatalogRead,
    GrocerySubscriptionCreate,
    GrocerySubscriptionRead,
    GrocerySubscriptionUpdate,
    GrocerySubscriptionCheckout,
    MarketplaceProductRead,
)
from api.v1.schema.order import OrderRead
from api.v1.services.marketplace import MarketplaceService
from api.v1.services.user import UserService

router = APIRouter(prefix="/marketplace", tags=["marketplace"])
security = HTTPBearer()


def _get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = credentials.credentials
    if UserService.is_token_blacklisted(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is blacklisted")
    try:
        payload = UserService.decode_access_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def get_marketplace_service(db: Session = Depends(get_db)) -> MarketplaceService:
    return MarketplaceService(db)


@router.get("/aisles", response_model=list[GroceryAisleRead])
def list_aisles(service: MarketplaceService = Depends(get_marketplace_service)):
    """Grocery aisles for the FUDS Marketplace home."""
    return service.list_aisles()


@router.get("/catalog", response_model=GroceryCatalogRead)
def grocery_catalog(
    aisle: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    """Milo, milk, cereals, staples, and other grocery necessities."""
    return service.catalog(aisle=aisle, search=search)


@router.get("/essentials", response_model=list[MarketplaceProductRead])
def grocery_essentials(
    search: Optional[str] = Query(None),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    """Suggested grocery essentials for creating a shopping list."""
    return service.catalog(search=search).products


@router.get("/subscriptions", response_model=list[GrocerySubscriptionRead])
def list_subscriptions(
    current_user: User = Depends(_get_current_user),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.list_subscriptions(current_user.id)


@router.post(
    "/subscriptions",
    response_model=GrocerySubscriptionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_subscription(
    payload: GrocerySubscriptionCreate,
    current_user: User = Depends(_get_current_user),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.create_subscription(current_user.id, payload)


@router.patch("/subscriptions/{sub_id}", response_model=GrocerySubscriptionRead)
def update_subscription(
    sub_id: int,
    payload: GrocerySubscriptionUpdate,
    current_user: User = Depends(_get_current_user),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    return service.update_subscription(current_user.id, sub_id, payload)


@router.delete("/subscriptions/{sub_id}", status_code=status.HTTP_200_OK)
def cancel_subscription(
    sub_id: int,
    current_user: User = Depends(_get_current_user),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    service.cancel_subscription(current_user.id, sub_id)
    return {"message": "Grocery roster cancelled"}


@router.post(
    "/subscriptions/{sub_id}/checkout",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
)
def checkout_subscription(
    sub_id: int,
    payload: GrocerySubscriptionCheckout = GrocerySubscriptionCheckout(),
    current_user: User = Depends(_get_current_user),
    service: MarketplaceService = Depends(get_marketplace_service),
):
    """Turn a grocery roster into a parent order (first / next delivery)."""
    return service.checkout(current_user.id, sub_id, payload.cycles)
