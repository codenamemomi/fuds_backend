"""
Paystack payment service.

Supported methods:
  1. Card / hosted checkout — POST /transaction/initialize → authorization_url
  2. Bank transfer (standard Pay with Transfer) — same Initialize Transaction API
     with channels=["bank_transfer"]. Paystack shows a temporary transfer account
     on the hosted checkout page (no Dedicated NUBAN / Titan DVA).

Flow (transfer):
  1. Checkout → parent Order (payment_status=pending)
  2. Client POST /payments/transfer/initialize → authorization_url
  3. Customer opens hosted page, transfers to the temporary account Paystack shows
  4. Webhook charge.success (channel bank_transfer) or client verify confirms payment
  5. Payment + parent/sub-orders marked paid
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Optional

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.utils.settings import settings
from api.v1.models.order import Order
from api.v1.models.payment import Payment, PaymentMethod, PaymentProvider, PaymentStatus
from api.v1.models.user import User
from api.v1.schema.payment import (
    InitializePaymentRequest,
    InitializePaymentResponse,
    InitializeTransferRequest,
    InitializeTransferResponse,
    PaymentRead,
    TransferAccountDetails,
    VerifyPaymentResponse,
)

logger = logging.getLogger(__name__)


def naira_to_kobo(amount_naira: float) -> int:
    """Paystack expects integer kobo (NGN * 100)."""
    return int(round(float(amount_naira) * 100))


class PaymentService:
    def __init__(self, db: Session):
        self.db = db

    # ─── Public API: hosted checkout ──────────────────────────────────────────

    def initialize(
        self,
        user: User,
        payload: InitializePaymentRequest,
    ) -> InitializePaymentResponse:
        self._ensure_configured()

        order = self._get_payable_order(payload.order_id, user.id)
        self._assert_order_unpaid(order)

        existing = (
            self.db.query(Payment)
            .filter(
                Payment.order_id == order.id,
                Payment.user_id == user.id,
                Payment.status == PaymentStatus.PENDING.value,
                Payment.payment_method == PaymentMethod.CARD.value,
                Payment.authorization_url.isnot(None),
            )
            .order_by(Payment.created_at.desc())
            .first()
        )
        if existing and existing.authorization_url and existing.access_code:
            return self._to_initialize_response(existing)

        email = self._require_email(user)
        amount = self._require_positive_amount(order)
        amount_kobo = naira_to_kobo(amount)
        reference = self._generate_reference(order.id, prefix="fuds")
        callback_url = payload.callback_url or settings.PAYSTACK_CALLBACK_URL

        payment = Payment(
            user_id=user.id,
            order_id=order.id,
            amount=amount,
            amount_kobo=amount_kobo,
            currency=settings.PAYSTACK_CURRENCY,
            provider=PaymentProvider.PAYSTACK.value,
            payment_method=PaymentMethod.CARD.value,
            reference=reference,
            status=PaymentStatus.PENDING.value,
            channel="card",
            metadata_json={
                "order_id": order.id,
                "user_id": user.id,
                "callback_url": callback_url,
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(payment)
        self.db.flush()

        body = {
            "email": email,
            "amount": amount_kobo,
            "currency": settings.PAYSTACK_CURRENCY,
            "reference": reference,
            "callback_url": callback_url,
            "metadata": {
                "order_id": order.id,
                "user_id": user.id,
                "payment_id": payment.id,
                "payment_method": PaymentMethod.CARD.value,
                "custom_fields": [
                    {
                        "display_name": "Order ID",
                        "variable_name": "order_id",
                        "value": str(order.id),
                    },
                    {
                        "display_name": "Customer",
                        "variable_name": "customer_name",
                        "value": user.fullname,
                    },
                ],
            },
        }

        try:
            data = self._paystack_request("POST", "/transaction/initialize", json_body=body)
        except HTTPException:
            self.db.rollback()
            raise

        payment.access_code = data.get("access_code")
        payment.authorization_url = data.get("authorization_url")
        if data.get("reference"):
            payment.reference = data["reference"]
        payment.raw_response = data
        payment.updated_at = datetime.utcnow()
        payment.metadata_json = {**(payment.metadata_json or {}), "payment_id": payment.id}

        self.db.commit()
        self.db.refresh(payment)
        return self._to_initialize_response(payment)

    # ─── Public API: bank transfer (Pay with Transfer, no Dedicated NUBAN) ────

    def initialize_bank_transfer(
        self,
        user: User,
        payload: InitializeTransferRequest,
    ) -> InitializeTransferResponse:
        """
        Start standard Paystack Pay with Transfer via Initialize Transaction.

        Sends channels=["bank_transfer"] so checkout only offers bank transfer.
        Paystack generates a temporary transfer account on the hosted page —
        no Dedicated NUBAN / Titan DVA provisioning.
        """
        self._ensure_configured()

        order = self._get_payable_order(payload.order_id, user.id)
        self._assert_order_unpaid(order)

        existing = (
            self.db.query(Payment)
            .filter(
                Payment.order_id == order.id,
                Payment.user_id == user.id,
                Payment.status == PaymentStatus.PENDING.value,
                Payment.payment_method == PaymentMethod.BANK_TRANSFER.value,
                Payment.authorization_url.isnot(None),
            )
            .order_by(Payment.created_at.desc())
            .first()
        )
        if existing and existing.authorization_url and existing.access_code:
            return self._to_transfer_response(existing)

        email = self._require_email(user)
        amount = self._require_positive_amount(order)
        amount_kobo = naira_to_kobo(amount)
        reference = self._generate_reference(order.id, prefix="fuds_trf")
        callback_url = payload.callback_url or settings.PAYSTACK_CALLBACK_URL

        payment = Payment(
            user_id=user.id,
            order_id=order.id,
            amount=amount,
            amount_kobo=amount_kobo,
            currency=settings.PAYSTACK_CURRENCY,
            provider=PaymentProvider.PAYSTACK.value,
            payment_method=PaymentMethod.BANK_TRANSFER.value,
            reference=reference,
            status=PaymentStatus.PENDING.value,
            channel="bank_transfer",
            metadata_json={
                "order_id": order.id,
                "user_id": user.id,
                "callback_url": callback_url,
                "payment_method": PaymentMethod.BANK_TRANSFER.value,
                "channels": ["bank_transfer"],
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(payment)
        self.db.flush()

        body = {
            "email": email,
            "amount": amount_kobo,
            "currency": settings.PAYSTACK_CURRENCY,
            "reference": reference,
            "callback_url": callback_url,
            # Standard Pay with Transfer — temporary account on hosted checkout
            "channels": ["bank_transfer"],
            "metadata": {
                "order_id": order.id,
                "user_id": user.id,
                "payment_id": payment.id,
                "payment_method": PaymentMethod.BANK_TRANSFER.value,
                "custom_fields": [
                    {
                        "display_name": "Order ID",
                        "variable_name": "order_id",
                        "value": str(order.id),
                    },
                    {
                        "display_name": "Customer",
                        "variable_name": "customer_name",
                        "value": user.fullname,
                    },
                ],
            },
        }

        try:
            data = self._paystack_request("POST", "/transaction/initialize", json_body=body)
        except HTTPException:
            self.db.rollback()
            raise

        payment.access_code = data.get("access_code")
        payment.authorization_url = data.get("authorization_url")
        if data.get("reference"):
            payment.reference = data["reference"]
        payment.raw_response = data
        payment.updated_at = datetime.utcnow()
        payment.metadata_json = {**(payment.metadata_json or {}), "payment_id": payment.id}

        self.db.commit()
        self.db.refresh(payment)

        logger.info(
            "Initialized bank_transfer payment %s for order %s (hosted checkout)",
            payment.reference,
            order.id,
        )
        return self._to_transfer_response(payment)

    def verify(
        self,
        reference: str,
        user_id: Optional[int] = None,
    ) -> VerifyPaymentResponse:
        """
        Confirm a transaction with Paystack and update local payment + order.

        Works for card and bank_transfer (same /transaction/verify reference).
        Clients should call this after the user closes the hosted checkout.
        """
        self._ensure_configured()

        payment = self.db.query(Payment).filter(Payment.reference == reference).first()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found for this reference",
            )
        if user_id is not None and payment.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Payment does not belong to this user",
            )

        if payment.status == PaymentStatus.SUCCESS.value:
            order = self.db.query(Order).filter(Order.id == payment.order_id).first()
            return VerifyPaymentResponse(
                payment=PaymentRead.model_validate(payment),
                order_payment_status=order.payment_status if order else "paid",
                message="Payment already confirmed",
            )

        try:
            data = self._paystack_request("GET", f"/transaction/verify/{reference}")
            payment = self._apply_paystack_transaction(payment, data)
        except HTTPException as exc:
            if payment.payment_method == PaymentMethod.BANK_TRANSFER.value and exc.status_code == 502:
                order = self.db.query(Order).filter(Order.id == payment.order_id).first()
                return VerifyPaymentResponse(
                    payment=PaymentRead.model_validate(payment),
                    order_payment_status=order.payment_status if order else "pending",
                    message=(
                        "Transfer not confirmed yet. Complete payment on the Paystack page "
                        "(temporary account). Status updates when funds arrive or you verify again."
                    ),
                )
            raise

        order = self.db.query(Order).filter(Order.id == payment.order_id).first()
        order_status = order.payment_status if order else payment.status
        message = (
            "Payment successful"
            if payment.status == PaymentStatus.SUCCESS.value
            else f"Payment {payment.status}"
        )
        return VerifyPaymentResponse(
            payment=PaymentRead.model_validate(payment),
            order_payment_status=order_status,
            message=message,
        )

    def handle_webhook(self, raw_body: bytes, signature: Optional[str]) -> dict[str, str]:
        """
        Process Paystack webhook (HMAC SHA512).
        Handles charge.success for card and bank_transfer.
        """
        self._ensure_configured()

        if not signature or not self.verify_webhook_signature(raw_body, signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Paystack signature",
            )

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook payload",
            ) from exc

        event = payload.get("event")
        data = payload.get("data") or {}

        if event == "charge.success":
            payment = self._resolve_payment_from_charge(data)
            if not payment:
                logger.warning(
                    "Webhook charge.success unmatched ref=%s amount=%s",
                    data.get("reference"),
                    data.get("amount"),
                )
                return {"status": "ok", "message": "ignored: payment not found"}
            self._apply_paystack_transaction(payment, data)
            return {"status": "ok", "message": "charge.success processed"}

        if event in ("charge.failed", "transfer.failed"):
            reference = data.get("reference")
            payment = (
                self.db.query(Payment).filter(Payment.reference == reference).first()
                if reference
                else None
            )
            if payment:
                payment.status = PaymentStatus.FAILED.value
                payment.provider_status = data.get("status") or "failed"
                payment.gateway_response = data.get("gateway_response")
                payment.raw_response = data
                payment.updated_at = datetime.utcnow()
                self.db.commit()
            return {"status": "ok", "message": f"{event} processed"}

        return {"status": "ok", "message": f"ignored event: {event}"}

    def get_payment(self, payment_id: int, user_id: int) -> PaymentRead:
        payment = (
            self.db.query(Payment)
            .filter(Payment.id == payment_id, Payment.user_id == user_id)
            .first()
        )
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        return PaymentRead.model_validate(payment)

    def list_payments(self, user_id: int) -> list[PaymentRead]:
        rows = (
            self.db.query(Payment)
            .filter(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .all()
        )
        return [PaymentRead.model_validate(p) for p in rows]

    @staticmethod
    def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
        secret = settings.PAYSTACK_SECRET_KEY.encode("utf-8")
        digest = hmac.new(secret, raw_body, hashlib.sha512).hexdigest()
        return hmac.compare_digest(digest, signature)

    def _resolve_payment_from_charge(self, data: dict[str, Any]) -> Optional[Payment]:
        """
        Match webhook charge payload to a local Payment.

        Order of attempts:
          1. Exact reference match
          2. metadata.payment_id / metadata.order_id
          3. pending payment by user email + amount_kobo (fallback)
        """
        reference = data.get("reference")
        if reference:
            payment = self.db.query(Payment).filter(Payment.reference == reference).first()
            if payment:
                return payment

        metadata = data.get("metadata") or {}
        if isinstance(metadata, dict):
            payment_id = metadata.get("payment_id")
            if payment_id:
                try:
                    payment = self.db.query(Payment).filter(Payment.id == int(payment_id)).first()
                except (TypeError, ValueError):
                    payment = None
                if payment:
                    return payment
            order_id = metadata.get("order_id")
            if order_id:
                try:
                    oid = int(order_id)
                except (TypeError, ValueError):
                    oid = None
                if oid is not None:
                    payment = (
                        self.db.query(Payment)
                        .filter(
                            Payment.order_id == oid,
                            Payment.status == PaymentStatus.PENDING.value,
                        )
                        .order_by(Payment.created_at.desc())
                        .first()
                    )
                    if payment:
                        return payment

        amount_kobo = data.get("amount")
        customer = data.get("customer") or {}
        email = customer.get("email")

        if amount_kobo is not None and email:
            user = self.db.query(User).filter(User.email == email).first()
            if user:
                payment = (
                    self.db.query(Payment)
                    .filter(
                        Payment.user_id == user.id,
                        Payment.status == PaymentStatus.PENDING.value,
                        Payment.amount_kobo == int(amount_kobo),
                    )
                    .order_by(Payment.created_at.asc())
                    .first()
                )
                if payment:
                    return payment

        return None

    # ─── Internals ────────────────────────────────────────────────────────────

    def _ensure_configured(self) -> None:
        if not settings.PAYSTACK_SECRET_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Paystack is not configured. Set PAYSTACK_SECRET_KEY in .env",
            )

    def _generate_reference(self, order_id: int, prefix: str = "fuds") -> str:
        # Paystack references: alphanumeric + underscore/dash; keep short
        safe_prefix = re.sub(r"[^a-zA-Z0-9_]", "", prefix)[:20]
        return f"{safe_prefix}_{order_id}_{uuid.uuid4().hex[:12]}"

    def _require_email(self, user: User) -> str:
        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user email is required for Paystack payments",
            )
        return user.email

    def _assert_order_unpaid(self, order: Order) -> None:
        if order.payment_status == "paid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order is already paid",
            )

    def _require_positive_amount(self, order: Order) -> float:
        amount = float(order.total_price)
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order total must be greater than zero",
            )
        return amount

    def _get_payable_order(self, order_id: int, user_id: int) -> Order:
        order = (
            self.db.query(Order)
            .filter(
                Order.id == order_id,
                Order.user_id == user_id,
                Order.parent_order_id.is_(None),
            )
            .first()
        )
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found (must be a parent order you own)",
            )
        return order

    def _paystack_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
        }

    def _paystack_request(
        self,
        method: str,
        path: str,
        json_body: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        url = f"{settings.PAYSTACK_BASE_URL.rstrip('/')}{path}"
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.request(
                    method,
                    url,
                    headers=self._paystack_headers(),
                    json=json_body,
                )
        except httpx.RequestError as exc:
            logger.exception("Paystack network error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to reach Paystack",
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid response from Paystack",
            ) from exc

        if response.status_code >= 400 or not payload.get("status"):
            message = payload.get("message") or "Paystack request failed"
            logger.warning("Paystack error %s: %s", response.status_code, message)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=message,
            )

        data = payload.get("data")
        if data is None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Paystack returned no data",
            )
        return data

    def _apply_paystack_transaction(
        self,
        payment: Payment,
        data: dict[str, Any],
    ) -> Payment:
        provider_status = (data.get("status") or "").lower()
        payment.provider_status = provider_status
        if data.get("channel"):
            payment.channel = data.get("channel")
        payment.gateway_response = data.get("gateway_response")
        payment.raw_response = data
        payment.updated_at = datetime.utcnow()

        tx_id = data.get("id")
        if tx_id is not None:
            payment.provider_transaction_id = str(tx_id)

        paid_kobo = data.get("amount")
        if paid_kobo is not None and int(paid_kobo) != int(payment.amount_kobo):
            # Underpayment / overpayment: do not auto-confirm
            logger.error(
                "Amount mismatch for payment %s: expected %s kobo, got %s",
                payment.id,
                payment.amount_kobo,
                paid_kobo,
            )
            payment.gateway_response = (
                f"Amount mismatch: expected {payment.amount_kobo} kobo, got {paid_kobo}"
            )
            # Keep pending so ops can reconcile; only hard-fail overpayment? Keep pending.
            if int(paid_kobo) < int(payment.amount_kobo):
                payment.status = PaymentStatus.PENDING.value
            else:
                # Overpayment still credits — mark success but note mismatch
                payment.status = PaymentStatus.SUCCESS.value
                payment.paid_at = datetime.utcnow()
                self._mark_order_paid(payment.order_id)
            self.db.commit()
            self.db.refresh(payment)
            return payment

        if provider_status == "success":
            payment.status = PaymentStatus.SUCCESS.value
            paid_at_raw = data.get("paid_at") or data.get("paidAt")
            if paid_at_raw:
                try:
                    payment.paid_at = datetime.fromisoformat(
                        str(paid_at_raw).replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except ValueError:
                    payment.paid_at = datetime.utcnow()
            else:
                payment.paid_at = datetime.utcnow()
            self._mark_order_paid(payment.order_id)
        elif provider_status in ("failed", "reversed"):
            payment.status = PaymentStatus.FAILED.value
        elif provider_status == "abandoned":
            payment.status = PaymentStatus.ABANDONED.value
        else:
            payment.status = PaymentStatus.PENDING.value

        self.db.commit()
        self.db.refresh(payment)
        return payment

    def _mark_order_paid(self, order_id: int) -> None:
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return

        order.payment_status = "paid"
        if order.status == "pending":
            order.status = "confirmed"

        for sub in order.sub_orders or []:
            sub.payment_status = "paid"
            if sub.status == "pending":
                sub.status = "confirmed"

    @staticmethod
    def _to_initialize_response(payment: Payment) -> InitializePaymentResponse:
        return InitializePaymentResponse(
            payment_id=payment.id,
            order_id=payment.order_id,
            reference=payment.reference,
            access_code=payment.access_code or "",
            authorization_url=payment.authorization_url or "",
            amount=float(payment.amount),
            amount_kobo=payment.amount_kobo,
            currency=payment.currency,
            status=payment.status,
            payment_method=payment.payment_method or PaymentMethod.CARD.value,
        )

    @staticmethod
    def _to_transfer_response(payment: Payment) -> InitializeTransferResponse:
        amount_fmt = f"₦{float(payment.amount):,.2f}"
        instructions = (
            f"Open the Paystack checkout and pay {amount_fmt} via bank transfer. "
            f"Paystack will show a temporary account for this payment. "
            f"Your order confirms automatically once the transfer succeeds. "
            f"Reference: {payment.reference}."
        )
        account = None
        if payment.account_number:
            account = TransferAccountDetails(
                account_number=payment.account_number,
                account_name=payment.account_name or "",
                bank_name=payment.bank_name or "",
                bank_slug=payment.bank_slug,
            )
        return InitializeTransferResponse(
            payment_id=payment.id,
            order_id=payment.order_id,
            reference=payment.reference,
            access_code=payment.access_code or "",
            authorization_url=payment.authorization_url or "",
            amount=float(payment.amount),
            amount_kobo=payment.amount_kobo,
            currency=payment.currency,
            status=payment.status,
            payment_method=PaymentMethod.BANK_TRANSFER.value,
            channel="bank_transfer",
            account=account,
            instructions=instructions,
            expires_hint=(
                "Complete transfer on the Paystack page; the temporary account expires "
                "after the checkout session."
            ),
        )
