"""Payment endpoints — Paystack card, Titan bank transfer, verify, webhook."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.v1.models.user import User
from api.v1.schema.payment import (
    InitializePaymentRequest,
    InitializePaymentResponse,
    InitializeTransferRequest,
    InitializeTransferResponse,
    PaymentRead,
    VerifyPaymentResponse,
    WebhookAck,
)
from api.v1.services.payment import PaymentService
from api.v1.services.user import UserService

router = APIRouter(prefix="/payments", tags=["payments"])
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


def get_payment_service(db: Session = Depends(get_db)) -> PaymentService:
    return PaymentService(db)


@router.post(
    "/initialize",
    response_model=InitializePaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def initialize_payment(
    payload: InitializePaymentRequest,
    current_user: User = Depends(_get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """
    Create a Paystack hosted transaction (card etc.) for a parent order.
    Returns `authorization_url` for the client to open (WebView / browser).
    """
    return service.initialize(current_user, payload)


@router.post(
    "/transfer/initialize",
    response_model=InitializeTransferResponse,
    status_code=status.HTTP_201_CREATED,
)
def initialize_bank_transfer(
    payload: InitializeTransferRequest,
    current_user: User = Depends(_get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """
    Pay with transfer via Paystack Titan dedicated virtual account.

    Creates (or reuses) a Titan DVA for the customer and returns account details
    so they can transfer the exact order amount from any Nigerian bank.
    Confirmation is via Paystack webhook (`charge.success`).
    """
    return service.initialize_bank_transfer(current_user, payload)


@router.get("/verify/{reference}", response_model=VerifyPaymentResponse)
def verify_payment(
    reference: str,
    current_user: User = Depends(_get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """
    Confirm payment status with Paystack (or local state for Titan transfers).
    Updates payment + order when successful.
    """
    return service.verify(reference, user_id=current_user.id)


@router.post("/webhook", response_model=WebhookAck)
async def paystack_webhook(
    request: Request,
    service: PaymentService = Depends(get_payment_service),
    x_paystack_signature: str | None = Header(default=None, alias="x-paystack-signature"),
):
    """
    Paystack server-to-server webhook.
    Configure URL in dashboard: POST /api/v1/payments/webhook

    Required for Titan DVA (dedicated_nuban) settlement.
    """
    raw = await request.body()
    result = service.handle_webhook(raw, x_paystack_signature)
    return WebhookAck(status=result.get("status", "ok"), message=result.get("message", "received"))


@router.get("", response_model=list[PaymentRead])
def list_my_payments(
    current_user: User = Depends(_get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """List the authenticated user's payment attempts (newest first)."""
    return service.list_payments(current_user.id)


@router.get("/{payment_id}", response_model=PaymentRead)
def get_payment(
    payment_id: int,
    current_user: User = Depends(_get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """Fetch a single payment by id (must belong to the caller)."""
    return service.get_payment(payment_id, current_user.id)
