"""
Unit tests for Paystack payment service and routes.
Paystack HTTP calls are mocked — no real network.
"""
import hashlib
import hmac
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.db.session import get_db
from api.utils.settings import settings
from api.v1.models import Base
from api.v1.models.order import Order
from api.v1.models.payment import Payment, PaymentMethod, PaymentStatus
from api.v1.models.user import User
from api.v1.schema.payment import InitializeTransferRequest
from api.v1.services.payment import PaymentService, naira_to_kobo
from main import app

SQLITE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def user(db) -> User:
    u = User(
        fullname="Pay Tester",
        phone="+2348012345678",
        email="pay@example.com",
        password_hash="x",
        phone_verified=True,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def order(db, user) -> Order:
    o = Order(
        user_id=user.id,
        status="pending",
        payment_status="pending",
        total_price=2500.00,
        created_at=datetime.utcnow(),
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


@pytest.fixture(autouse=True)
def paystack_secret(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_test_dummy_secret")
    monkeypatch.setattr(settings, "PAYSTACK_PUBLIC_KEY", "pk_test_dummy")
    monkeypatch.setattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co")
    monkeypatch.setattr(settings, "PAYSTACK_CALLBACK_URL", "http://localhost/callback")
    monkeypatch.setattr(settings, "PAYSTACK_CURRENCY", "NGN")
    monkeypatch.setattr(settings, "PAYSTACK_TRANSFER_BANK", "titan-paystack")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def test_naira_to_kobo():
    assert naira_to_kobo(2500) == 250_000
    assert naira_to_kobo(2500.50) == 250_050
    assert naira_to_kobo(0.01) == 1


# ─── Service ─────────────────────────────────────────────────────────────────

class TestPaymentServiceInitialize:
    def test_initialize_creates_payment_and_calls_paystack(self, db, user, order):
        service = PaymentService(db)
        mock_data = {
            "authorization_url": "https://checkout.paystack.com/abc",
            "access_code": "ACCESS_CODE",
            "reference": f"fuds_{order.id}_testref",
        }

        with patch.object(service, "_paystack_request", return_value=mock_data) as mock_req:
            from api.v1.schema.payment import InitializePaymentRequest

            result = service.initialize(
                user,
                InitializePaymentRequest(order_id=order.id),
            )

        mock_req.assert_called_once()
        assert result.authorization_url == mock_data["authorization_url"]
        assert result.access_code == "ACCESS_CODE"
        assert result.amount == 2500.0
        assert result.amount_kobo == 250_000
        assert result.status == PaymentStatus.PENDING.value

        payment = db.query(Payment).filter(Payment.order_id == order.id).first()
        assert payment is not None
        assert payment.user_id == user.id
        assert payment.amount_kobo == 250_000

    def test_initialize_rejects_already_paid_order(self, db, user, order):
        order.payment_status = "paid"
        db.commit()
        service = PaymentService(db)
        from api.v1.schema.payment import InitializePaymentRequest
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            service.initialize(user, InitializePaymentRequest(order_id=order.id))
        assert exc.value.status_code == 400


class TestPaymentServiceVerify:
    def test_verify_success_marks_order_paid(self, db, user, order):
        payment = Payment(
            user_id=user.id,
            order_id=order.id,
            amount=2500.0,
            amount_kobo=250_000,
            currency="NGN",
            provider="paystack",
            reference="fuds_ref_success",
            status=PaymentStatus.PENDING.value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(payment)
        db.commit()

        service = PaymentService(db)
        verify_data = {
            "id": 98765,
            "status": "success",
            "amount": 250_000,
            "channel": "card",
            "gateway_response": "Successful",
            "paid_at": "2026-07-13T12:00:00.000Z",
            "reference": "fuds_ref_success",
        }

        with patch.object(service, "_paystack_request", return_value=verify_data):
            result = service.verify("fuds_ref_success", user_id=user.id)

        assert result.payment.status == PaymentStatus.SUCCESS.value
        assert result.order_payment_status == "paid"
        db.refresh(order)
        assert order.payment_status == "paid"
        assert order.status == "confirmed"

    def test_verify_amount_mismatch_fails(self, db, user, order):
        payment = Payment(
            user_id=user.id,
            order_id=order.id,
            amount=2500.0,
            amount_kobo=250_000,
            currency="NGN",
            provider="paystack",
            reference="fuds_ref_mismatch",
            status=PaymentStatus.PENDING.value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(payment)
        db.commit()

        service = PaymentService(db)
        verify_data = {
            "id": 1,
            "status": "success",
            "amount": 100,  # wrong
            "reference": "fuds_ref_mismatch",
        }

        with patch.object(service, "_paystack_request", return_value=verify_data):
            result = service.verify("fuds_ref_mismatch", user_id=user.id)

        # Underpayment stays pending for reconciliation (not auto-failed)
        assert result.payment.status == PaymentStatus.PENDING.value
        assert "Amount mismatch" in (result.payment.gateway_response or "")
        db.refresh(order)
        assert order.payment_status == "pending"


class TestWebhook:
    def test_webhook_signature_and_charge_success(self, db, user, order):
        payment = Payment(
            user_id=user.id,
            order_id=order.id,
            amount=2500.0,
            amount_kobo=250_000,
            currency="NGN",
            provider="paystack",
            reference="fuds_webhook_ref",
            status=PaymentStatus.PENDING.value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(payment)
        db.commit()

        body = {
            "event": "charge.success",
            "data": {
                "id": 111,
                "status": "success",
                "amount": 250_000,
                "channel": "card",
                "gateway_response": "Successful",
                "reference": "fuds_webhook_ref",
                "paid_at": "2026-07-13T12:00:00.000Z",
            },
        }
        raw = json.dumps(body).encode("utf-8")
        sig = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
            raw,
            hashlib.sha512,
        ).hexdigest()

        service = PaymentService(db)
        result = service.handle_webhook(raw, sig)
        assert result["status"] == "ok"

        db.refresh(payment)
        db.refresh(order)
        assert payment.status == PaymentStatus.SUCCESS.value
        assert order.payment_status == "paid"

    def test_webhook_rejects_bad_signature(self, db):
        service = PaymentService(db)
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            service.handle_webhook(b'{"event":"charge.success"}', "bad-signature")
        assert exc.value.status_code == 401


class TestTitanBankTransfer:
    def test_initialize_transfer_creates_dva_and_payment(self, db, user, order):
        service = PaymentService(db)

        def fake_request(method, path, json_body=None):
            if path == "/customer":
                return {"customer_code": "CUS_titan_test", "email": user.email}
            if path == "/dedicated_account":
                assert json_body["preferred_bank"] == "titan-paystack"
                assert json_body["customer"] == "CUS_titan_test"
                return {
                    "id": 999,
                    "account_number": "9876543210",
                    "account_name": "Pay Tester",
                    "bank": {"name": "Titan Paystack", "slug": "titan-paystack"},
                }
            raise AssertionError(f"Unexpected Paystack call {method} {path}")

        with patch.object(service, "_paystack_request", side_effect=fake_request):
            result = service.initialize_bank_transfer(
                user, InitializeTransferRequest(order_id=order.id)
            )

        assert result.payment_method == PaymentMethod.BANK_TRANSFER.value
        assert result.account.account_number == "9876543210"
        assert result.account.bank_name == "Titan Paystack"
        assert result.amount_kobo == 250_000
        assert "Transfer exactly" in result.instructions

        db.refresh(user)
        assert user.paystack_customer_code == "CUS_titan_test"
        assert user.paystack_dva_account_number == "9876543210"

        payment = db.query(Payment).filter(Payment.order_id == order.id).first()
        assert payment.payment_method == PaymentMethod.BANK_TRANSFER.value
        assert payment.account_number == "9876543210"
        assert payment.paystack_customer_code == "CUS_titan_test"

    def test_initialize_transfer_reuses_existing_dva(self, db, user, order):
        user.paystack_customer_code = "CUS_existing"
        user.paystack_dva_account_number = "1111222233"
        user.paystack_dva_account_name = "Pay Tester"
        user.paystack_dva_bank_name = "Titan Paystack"
        user.paystack_dva_bank_slug = "titan-paystack"
        db.commit()

        service = PaymentService(db)
        with patch.object(service, "_paystack_request") as mock_req:
            result = service.initialize_bank_transfer(
                user, InitializeTransferRequest(order_id=order.id)
            )

        mock_req.assert_not_called()
        assert result.account.account_number == "1111222233"

    def test_webhook_matches_dva_by_customer_and_amount(self, db, user, order):
        payment = Payment(
            user_id=user.id,
            order_id=order.id,
            amount=2500.0,
            amount_kobo=250_000,
            currency="NGN",
            provider="paystack",
            payment_method=PaymentMethod.BANK_TRANSFER.value,
            reference="fuds_trf_local_ref",
            status=PaymentStatus.PENDING.value,
            channel="dedicated_nuban",
            account_number="9876543210",
            account_name="Pay Tester",
            bank_name="Titan Paystack",
            paystack_customer_code="CUS_titan_test",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(payment)
        db.commit()

        # Paystack DVA charges often use a different gateway reference
        body = {
            "event": "charge.success",
            "data": {
                "id": 555,
                "status": "success",
                "amount": 250_000,
                "channel": "dedicated_nuban",
                "gateway_response": "Successful",
                "reference": "paystack_auto_ref_xyz",
                "paid_at": "2026-07-13T12:00:00.000Z",
                "customer": {
                    "customer_code": "CUS_titan_test",
                    "email": "pay@example.com",
                },
            },
        }
        raw = json.dumps(body).encode("utf-8")
        sig = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
            raw,
            hashlib.sha512,
        ).hexdigest()

        service = PaymentService(db)
        result = service.handle_webhook(raw, sig)
        assert result["message"] == "charge.success processed"

        db.refresh(payment)
        db.refresh(order)
        assert payment.status == PaymentStatus.SUCCESS.value
        assert order.payment_status == "paid"
        assert order.status == "confirmed"


class TestPaymentRoutes:
    def test_initialize_requires_auth(self, client):
        resp = client.post("/api/v1/payments/initialize", json={"order_id": 1})
        assert resp.status_code in (401, 403)

    def test_transfer_initialize_requires_auth(self, client):
        resp = client.post("/api/v1/payments/transfer/initialize", json={"order_id": 1})
        assert resp.status_code in (401, 403)

    def test_webhook_endpoint_accepts_valid_signature(self, client, db, user, order):
        payment = Payment(
            user_id=user.id,
            order_id=order.id,
            amount=1000.0,
            amount_kobo=100_000,
            currency="NGN",
            provider="paystack",
            reference="route_webhook_ref",
            status=PaymentStatus.PENDING.value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(payment)
        db.commit()

        body = {
            "event": "charge.success",
            "data": {
                "id": 222,
                "status": "success",
                "amount": 100_000,
                "reference": "route_webhook_ref",
                "paid_at": "2026-07-13T12:00:00.000Z",
            },
        }
        raw = json.dumps(body).encode("utf-8")
        sig = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
            raw,
            hashlib.sha512,
        ).hexdigest()

        resp = client.post(
            "/api/v1/payments/webhook",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "x-paystack-signature": sig,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
