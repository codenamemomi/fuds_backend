"""User auth / profile schemas with password strength + confirm rules."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PASSWORD_MIN_LENGTH = 8

PASSWORD_HINTS = [
    f"At least {PASSWORD_MIN_LENGTH} characters",
    "At least one uppercase letter (A–Z)",
    "At least one lowercase letter (a–z)",
    "At least one number (0–9)",
]


def format_phone_number(phone: str) -> str:
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")

    if cleaned.startswith("+"):
        return "+" + "".join(c for c in cleaned[1:] if c.isdigit())

    if cleaned.startswith("0"):
        cleaned = cleaned[1:]

    if cleaned.startswith("234") and len(cleaned) >= 12:
        return f"+{cleaned}"

    return f"+234{cleaned}"


def validate_password_strength(password: str) -> str:
    """Raise ValueError with a clear message if password is weak."""
    if not isinstance(password, str):
        raise ValueError("Password must be a string")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must include at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must include at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must include at least one number")
    return password


class UserCreate(BaseModel):
    fullname: str = Field(..., min_length=2)
    phone: str = Field(..., min_length=7)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH)
    password_confirm: str = Field(..., min_length=PASSWORD_MIN_LENGTH)
    phone_verified: bool = False
    diet_goal: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Phone number must be a string")
        return format_phone_number(v)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)

    @model_validator(mode="after")
    def passwords_match(self) -> "UserCreate":
        if self.password != self.password_confirm:
            raise ValueError("password and password_confirm do not match")
        return self


class UserLogin(BaseModel):
    phone: str = Field(..., min_length=7)
    password: str = Field(..., min_length=1)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Phone number must be a string")
        return format_phone_number(v)


class UserVerifyOTP(BaseModel):
    email: str = Field(..., min_length=5)
    otp: str = Field(..., min_length=6, max_length=6)


class UserResendOTP(BaseModel):
    email: str = Field(..., min_length=5)


class UserUpdate(BaseModel):
    """Profile fields only — password changes go through ChangePasswordRequest."""

    fullname: Optional[str] = Field(None, min_length=2)
    phone: Optional[str] = Field(None, min_length=7)
    email: Optional[str] = Field(None, min_length=5)
    diet_goal: Optional[str] = None
    address: Optional[str] = None

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Phone number must be a string")
        return format_phone_number(v)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=PASSWORD_MIN_LENGTH)
    password_confirm: str = Field(..., min_length=PASSWORD_MIN_LENGTH)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.password_confirm:
            raise ValueError("new_password and password_confirm do not match")
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from the current password")
        return self


class UserRead(BaseModel):
    id: int
    fullname: str
    phone: str
    email: Optional[str] = None
    diet_goal: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    last_login_at: Optional[datetime] = None
    phone_verified: bool = False

    model_config = ConfigDict(from_attributes=True)
