from datetime import datetime, timedelta
import logging

import bcrypt
import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.utils.email_service import dispatch_registration_otp
from api.utils.otp import OTPService
from api.utils.redis_utils import redis_client
from api.utils.settings import settings
from api.v1.models.user import User
from api.v1.schema.user import (
    ChangePasswordRequest,
    UserCreate,
    UserLogin,
    UserRead,
    UserUpdate,
    UserResendOTP,
)
from api.v1.services.base import BaseService

logger = logging.getLogger(__name__)


class UserService(BaseService[User, UserCreate, UserRead]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def register(self, payload: UserCreate) -> User:
        if self.db.query(User).filter(User.phone == payload.phone).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already registered")

        if payload.email and self.db.query(User).filter(User.email == payload.email).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        if not payload.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required for account verification",
            )

        user_data = payload.model_dump(exclude={"password", "password_confirm"})
        user_data["password_hash"] = self.hash_password(payload.password)
        user_data["phone_verified"] = False
        user = self.model_class(**user_data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        # OTP lives in Redis; delivery goes through email queue (async) or inline
        self._issue_and_send_registration_otp(
            email=payload.email,
            fullname=payload.fullname,
            enforce_cooldown=False,
        )
        return user

    def verify_otp(self, email: str, otp: str) -> bool:
        email_norm = email.strip().lower()
        user = self.db.query(User).filter(User.email == email_norm).first()
        if not user:
            # Case-insensitive fallback for older rows
            user = (
                self.db.query(User)
                .filter(User.email.ilike(email_norm))
                .first()
            )
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        otp_service = OTPService()
        if not otp_service.is_valid(otp, purpose="registration", identifier=email_norm):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

        otp_service.consume(otp, purpose="registration", identifier=email_norm)
        user.phone_verified = True
        self.db.commit()
        self.db.refresh(user)
        return True

    def resend_otp(self, email: str) -> None:
        email_norm = email.strip().lower()
        user = self.db.query(User).filter(User.email == email_norm).first()
        if not user:
            user = (
                self.db.query(User)
                .filter(User.email.ilike(email_norm))
                .first()
            )
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if user.phone_verified:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is already verified")

        self._issue_and_send_registration_otp(
            email=email_norm,
            fullname=user.fullname,
            enforce_cooldown=True,
        )

    def _issue_and_send_registration_otp(
        self,
        *,
        email: str,
        fullname: str | None,
        enforce_cooldown: bool,
    ) -> None:
        """Create Redis OTP and dispatch email (queued when EMAIL_ASYNC)."""
        email_norm = email.strip().lower()
        if enforce_cooldown:
            cooldown_key = f"otp:resend_cooldown:{email_norm}"
            if redis_client.exists(cooldown_key):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Please wait {settings.OTP_RESEND_COOLDOWN_SECONDS}s "
                        "before requesting another code"
                    ),
                )

        otp_service = OTPService()
        otp_payload = otp_service.create_payload(
            purpose="registration",
            identifier=email_norm,
        )
        code = str(otp_payload["code"])

        try:
            dispatch_registration_otp(to=email_norm, code=code, fullname=fullname)
        except Exception as exc:
            # OTP remains in Redis either way.
            logger.exception("Failed to dispatch registration OTP to %s: %s", email_norm, exc)
            provider = (settings.EMAIL_PROVIDER or "console").lower()
            if settings.DEBUG or provider == "console":
                logger.warning("OTP for %s (dev fallback log): %s", email_norm, code)
            # Surface provider errors so Brevo/SMTP misconfig is visible to the client.
            detail = str(exc) if str(exc) else "Could not send verification email"
            if provider in ("brevo", "sendinblue", "smtp", "resend") or "Brevo" in detail:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        f"Email provider rejected the message: {detail}. "
                        "Check BREVO_API_KEY, EMAIL_FROM (must be a verified sender "
                        "in Brevo), and that the recipient is valid."
                    ),
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not send verification email. Please try again shortly.",
            ) from exc

        if enforce_cooldown:
            redis_client.setex(
                f"otp:resend_cooldown:{email_norm}",
                settings.OTP_RESEND_COOLDOWN_SECONDS,
                "1",
            )


    def login(self, payload: UserLogin) -> tuple[str, User]:
        user = self.db.query(User).filter(User.phone == payload.phone).first()
        if not user or not self.verify_password(payload.password, user.password_hash or ""):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if not user.phone_verified:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Please verify your email/phone number first")

        user.last_login_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        token = self._create_access_token(user)
        return token, user

    def update_profile(self, user: User, payload: UserUpdate) -> User:
        if payload.phone and payload.phone != user.phone:
            if self.db.query(User).filter(User.phone == payload.phone).first():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone number already registered")
            user.phone = payload.phone
            user.phone_verified = False

        if payload.email and payload.email != user.email:
            if self.db.query(User).filter(User.email == payload.email).first():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
            user.email = payload.email

        if payload.fullname is not None:
            user.fullname = payload.fullname

        if payload.diet_goal is not None:
            user.diet_goal = payload.diet_goal

        if payload.address is not None:
            user.address = payload.address

        self.db.commit()
        self.db.refresh(user)
        return user

    def change_password(self, user: User, payload: ChangePasswordRequest) -> None:
        if not user.password_hash or not self.verify_password(
            payload.current_password, user.password_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        user.password_hash = self.hash_password(payload.new_password)
        self.db.commit()
        self.db.refresh(user)

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash with the bcrypt library directly.

        Avoids passlib: passlib is unmaintained and breaks on bcrypt>=4.1
        (CI installs latest bcrypt → ValueError during wrap-bug detection).
        Output remains standard bcrypt hashes ($2b$...), compatible with
        hashes previously produced by passlib.
        """
        secret = password.encode("utf-8")
        # bcrypt only uses the first 72 bytes; normal app passwords are fine
        if len(secret) > 72:
            secret = secret[:72]
        return bcrypt.hashpw(secret, bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        if not hashed_password:
            return False
        try:
            secret = plain_password.encode("utf-8")
            if len(secret) > 72:
                secret = secret[:72]
            return bcrypt.checkpw(secret, hashed_password.encode("utf-8"))
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _create_access_token(user: User) -> str:
        now = datetime.utcnow()
        payload = {
            "sub": str(user.id),
            "phone": user.phone,
            "iat": now,
            "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def decode_access_token(token: str) -> dict:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    @staticmethod
    def blacklist_token(token: str) -> None:
        try:
            payload = UserService.decode_access_token(token)
            exp = payload.get("exp")
            if exp:
                now = datetime.utcnow().timestamp()
                ttl = int(exp - now)
                if ttl > 0:
                    from api.utils.redis_utils import redis_client
                    key = f"blacklist:token:{token}"
                    redis_client.setex(key, ttl, "true")
        except Exception:
            pass

    @staticmethod
    def is_token_blacklisted(token: str) -> bool:
        try:
            from api.utils.redis_utils import redis_client
            key = f"blacklist:token:{token}"
            return redis_client.exists(key) > 0
        except Exception:
            return False

