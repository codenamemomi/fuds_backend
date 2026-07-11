from datetime import datetime, timedelta

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from api.utils.otp import OTPService
from api.utils.settings import settings
from api.v1.models.user import User
from api.v1.schema.user import UserCreate, UserLogin, UserRead, UserUpdate, UserResendOTP
from api.v1.services.base import BaseService

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService(BaseService[User, UserCreate, UserRead]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def register(self, payload: UserCreate) -> User:
        if self.db.query(User).filter(User.phone == payload.phone).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already registered")

        if payload.email and self.db.query(User).filter(User.email == payload.email).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        user_data = payload.model_dump(exclude={"password"})
        user_data["password_hash"] = self.hash_password(payload.password)
        user_data["phone_verified"] = False
        user = self.model_class(**user_data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        # Generate and store OTP in Redis
        otp_service = OTPService()
        otp_payload = otp_service.create_payload(purpose="registration", identifier=payload.email)
        print(f"DEBUG: Generated registration OTP for {payload.email}: {otp_payload['code']}")

        return user

    def verify_otp(self, email: str, otp: str) -> bool:
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        otp_service = OTPService()
        if not otp_service.is_valid(otp, purpose="registration", identifier=email):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

        otp_service.consume(otp, purpose="registration", identifier=email)
        user.phone_verified = True
        self.db.commit()
        self.db.refresh(user)
        return True

    def resend_otp(self, email: str) -> None:
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if user.phone_verified:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is already verified")

        otp_service = OTPService()
        otp_payload = otp_service.create_payload(purpose="registration", identifier=email)
        print(f"DEBUG: Resent registration OTP for {email}: {otp_payload['code']}")


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

        if payload.password is not None:
            user.password_hash = self.hash_password(payload.password)

        if payload.diet_goal is not None:
            user.diet_goal = payload.diet_goal

        if payload.address is not None:
            user.address = payload.address

        self.db.commit()
        self.db.refresh(user)
        return user

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

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

