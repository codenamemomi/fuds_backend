from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    fullname: str = Field(..., min_length=2)
    phone: str = Field(..., min_length=7)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=8)
    phone_verified: bool = False
    diet_goal: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True


class UserLogin(BaseModel):
    phone: str = Field(..., min_length=7)
    password: str = Field(..., min_length=8)


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
