import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.v1.routes.user as user_routes
from api.db.session import get_db
from api.v1.models.base_class import Base
from api.v1.services.user import UserService
from main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_user_service():
        db = TestingSessionLocal()
        try:
            yield UserService(db)
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[user_routes.get_user_service] = override_get_user_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_register_and_login_flow(client):
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "fullname": "Jane Doe",
            "phone": "08012345678",
            "email": "jane@example.com",
            "password": "secret123",
        },
    )

    assert register_response.status_code == 201
    body = register_response.json()
    assert body["phone"] == "08012345678"
    assert body["email"] == "jane@example.com"
    assert "password_hash" not in body

    # Attempt login before verifying OTP (should fail with HTTP 403 Forbidden)
    login_unverified_response = client.post(
        "/api/v1/auth/login",
        json={"phone": "08012345678", "password": "secret123"},
    )
    assert login_unverified_response.status_code == 403
    assert "verify" in login_unverified_response.json()["detail"].lower()

    # Retrieve the OTP from Redis
    import json
    from api.utils.redis_utils import redis_client
    otp_key = "otp:registration:jane@example.com"
    raw_payload = redis_client.get(otp_key)
    assert raw_payload is not None
    otp_payload = json.loads(raw_payload)
    otp_code = otp_payload["code"]

    # Verify with an invalid OTP (should fail)
    verify_invalid_response = client.post(
        "/api/v1/auth/verify-otp",
        json={"email": "jane@example.com", "otp": "000000"},
    )
    assert verify_invalid_response.status_code == 400

    # Test resending OTP for nonexistent email (should fail with 404)
    resend_nonexistent_response = client.post(
        "/api/v1/auth/resend-otp",
        json={"email": "nonexistent@example.com"},
    )
    assert resend_nonexistent_response.status_code == 404

    # Test successful resending OTP
    resend_success_response = client.post(
        "/api/v1/auth/resend-otp",
        json={"email": "jane@example.com"},
    )
    assert resend_success_response.status_code == 200
    assert resend_success_response.json()["message"] == "OTP resent successfully."

    # Retrieve the newly generated OTP from Redis
    raw_payload_new = redis_client.get(otp_key)
    assert raw_payload_new is not None
    otp_payload_new = json.loads(raw_payload_new)
    new_otp_code = otp_payload_new["code"]

    # Verify with the new correct OTP (should succeed)
    verify_response = client.post(
        "/api/v1/auth/verify-otp",
        json={"email": "jane@example.com", "otp": new_otp_code},
    )
    assert verify_response.status_code == 200

    # Try to resend OTP for an already verified user (should fail with 400)
    resend_verified_response = client.post(
        "/api/v1/auth/resend-otp",
        json={"email": "jane@example.com"},
    )
    assert resend_verified_response.status_code == 400

    # Now login should succeed
    login_response = client.post(
        "/api/v1/auth/login",
        json={"phone": "08012345678", "password": "secret123"},
    )

    assert login_response.status_code == 200
    auth_body = login_response.json()
    access_token = auth_body["access_token"]
    assert access_token
    assert auth_body["user"]["phone"] == "08012345678"

    # Test /me endpoint with invalid token
    me_invalid_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid_token"},
    )
    assert me_invalid_response.status_code == 401

    # Test /me endpoint with missing token
    me_missing_response = client.get(
        "/api/v1/auth/me",
    )
    assert me_missing_response.status_code == 403

    # Test /me endpoint with valid token
    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    me_body = me_response.json()
    assert me_body["phone"] == "08012345678"
    assert me_body["email"] == "jane@example.com"

    # Test editing profile (PUT /me)
    edit_response = client.put(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "fullname": "Jane Doe Updated",
            "diet_goal": "Weight Loss",
            "address": "123 Lagos Way"
        }
    )
    assert edit_response.status_code == 200
    edit_body = edit_response.json()
    assert edit_body["fullname"] == "Jane Doe Updated"
    assert edit_body["diet_goal"] == "Weight Loss"
    assert edit_body["address"] == "123 Lagos Way"
    assert edit_body["phone_verified"] is True

    # Register a second user to test conflicts
    register2_response = client.post(
        "/api/v1/auth/register",
        json={
            "fullname": "Bob Smith",
            "phone": "09012345678",
            "email": "bob@example.com",
            "password": "secret123",
        },
    )
    assert register2_response.status_code == 201

    # Try to edit Jane's phone to Bob's phone (should fail with 409)
    edit_conflict_response = client.put(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "phone": "09012345678"
        }
    )
    assert edit_conflict_response.status_code == 409

    # Test editing phone resets verification status
    edit_phone_response = client.put(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "phone": "08087654321"
        }
    )
    assert edit_phone_response.status_code == 200
    edit_phone_body = edit_phone_response.json()
    assert edit_phone_body["phone"] == "08087654321"
    assert edit_phone_body["phone_verified"] is False

    # Test logout
    logout_response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Logged out successfully"


    # Accessing /me now with blacklisted token should fail
    me_after_logout_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_after_logout_response.status_code == 401

    # Attempting to logout again should fail as token is already blacklisted
    logout_again_response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_again_response.status_code == 401


