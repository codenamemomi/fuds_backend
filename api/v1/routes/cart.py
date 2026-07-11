from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.v1.models.user import User
from api.v1.schema.cart import CartItemCreate, CartItemUpdate, CartRead
from api.v1.services.cart import CartService
from api.v1.services.user import UserService

router = APIRouter(prefix="/cart", tags=["cart"])
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


def get_cart_service(db: Session = Depends(get_db)) -> CartService:
    return CartService(db)


@router.post("/add", response_model=CartRead, status_code=status.HTTP_200_OK)
def add_to_cart(
    item: CartItemCreate,
    current_user: User = Depends(_get_current_user),
    service: CartService = Depends(get_cart_service),
):
    """Add a product to the cart. Accumulates quantity if already present."""
    return service.add_item(current_user.id, item)


@router.get("", response_model=CartRead)
def view_cart(
    current_user: User = Depends(_get_current_user),
    service: CartService = Depends(get_cart_service),
):
    """View the current user's cart with enriched product details."""
    return service.get_cart(current_user.id)


@router.put("/update", response_model=CartRead)
def update_cart_item(
    update: CartItemUpdate,
    current_user: User = Depends(_get_current_user),
    service: CartService = Depends(get_cart_service),
):
    """Update quantity of a cart item. Set quantity to 0 to remove."""
    return service.update_item(current_user.id, update)


@router.delete("/item/{product_id}", response_model=CartRead)
def remove_cart_item(
    product_id: int,
    current_user: User = Depends(_get_current_user),
    service: CartService = Depends(get_cart_service),
):
    """Remove a specific product from the cart."""
    return service.remove_item(current_user.id, product_id)


@router.delete("", status_code=status.HTTP_200_OK)
def clear_cart(
    current_user: User = Depends(_get_current_user),
    service: CartService = Depends(get_cart_service),
):
    """Clear all items from the cart."""
    service.clear_cart(current_user.id)
    return {"message": "Cart cleared successfully"}
