from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.v1.models.user import User
from api.v1.schema.order import CheckoutRequest, OrderRead
from api.v1.services.order import OrderService
from api.v1.services.user import UserService

router = APIRouter(prefix="/orders", tags=["orders"])
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


def get_order_service(db: Session = Depends(get_db)) -> OrderService:
    return OrderService(db)


@router.post("/checkout", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def checkout(
    request: CheckoutRequest,
    current_user: User = Depends(_get_current_user),
    service: OrderService = Depends(get_order_service),
):
    """
    Convert cart into an order. Creates a parent order + one sub-order per vendor.
    Cart is cleared on success.
    """
    return service.checkout(current_user.id, request)


@router.get("", response_model=list[OrderRead])
def list_orders(
    current_user: User = Depends(_get_current_user),
    service: OrderService = Depends(get_order_service),
):
    """List the current user's orders (most recent first)."""
    return service.list_orders(current_user.id)


@router.get("/{order_id}", response_model=OrderRead)
def get_order(
    order_id: int,
    current_user: User = Depends(_get_current_user),
    service: OrderService = Depends(get_order_service),
):
    """Get a single order by ID (must belong to the current user)."""
    return service.get_order(order_id, current_user.id)
