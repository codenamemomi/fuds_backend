from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.v1.models.user import User
from api.v1.schema.user import (
    ChangePasswordRequest,
    UserCreate,
    UserLogin,
    UserRead,
    UserVerifyOTP,
    UserUpdate,
    UserResendOTP,
)
from api.v1.services.user import UserService

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


def _user_from_credentials(
    credentials: HTTPAuthorizationCredentials,
    db: Session,
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


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, service: UserService = Depends(get_user_service)):
    user = service.register(payload)
    token = service._create_access_token(user)
    return {"access_token": token, "token_type": "bearer", "user": UserRead.model_validate(user)}


@router.post("/verify-otp", status_code=status.HTTP_200_OK)
def verify_otp(payload: UserVerifyOTP, service: UserService = Depends(get_user_service)):
    service.verify_otp(payload.email, payload.otp)
    return {"message": "OTP verified successfully. Account is now active."}


@router.post("/resend-otp", status_code=status.HTTP_200_OK)
def resend_otp(payload: UserResendOTP, service: UserService = Depends(get_user_service)):
    service.resend_otp(payload.email)
    return {"message": "OTP resent successfully."}



@router.post("/login")
def login_user(payload: UserLogin, service: UserService = Depends(get_user_service)):
    token, user = service.login(payload)
    return {"access_token": token, "token_type": "bearer", "user": UserRead.model_validate(user)}


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = credentials.credentials
    if UserService.is_token_blacklisted(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has already been logged out")

    try:
        UserService.decode_access_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    UserService.blacklist_token(token)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserRead)
def get_current_user_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
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
    return UserRead.model_validate(user)


@router.put("/me", response_model=UserRead)
def update_user_profile(
    payload: UserUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    service: UserService = Depends(get_user_service),
):
    # Use service.db so the loaded User stays in the same session as the service
    user = _user_from_credentials(credentials, service.db)
    updated_user = service.update_profile(user, payload)
    return UserRead.model_validate(updated_user)


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    payload: ChangePasswordRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    service: UserService = Depends(get_user_service),
):
    """
    Change password for the authenticated user.
    Requires current_password, new_password, and password_confirm (must match).
    """
    user = _user_from_credentials(credentials, service.db)
    service.change_password(user, payload)
    return {"message": "Password changed successfully"}


