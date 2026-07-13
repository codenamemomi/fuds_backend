from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def format_phone_number(phone: str) -> str:
    # Remove all whitespace, hyphens, parentheses, etc.
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")
    
    if cleaned.startswith("+"):
        return "+" + "".join(c for c in cleaned[1:] if c.isdigit())
    
    if cleaned.startswith("0"):
        cleaned = cleaned[1:]
        
    if cleaned.startswith("234") and len(cleaned) >= 12:
        return f"+{cleaned}"
        
    return f"+234{cleaned}"


class UserCreate(BaseModel):
    fullname: str = Field(..., min_length=2)
    phone: str = Field(..., min_length=7)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=8)
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


class UserLogin(BaseModel):
    phone: str = Field(..., min_length=7)
    password: str = Field(..., min_length=8)

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
    fullname: Optional[str] = Field(None, min_length=2)
    phone: Optional[str] = Field(None, min_length=7)
    email: Optional[str] = Field(None, min_length=5)
    password: Optional[str] = Field(None, min_length=8)
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
