from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    fullname: str = Field(..., min_length=2)
    phone: str = Field(..., min_length=7)
    email: Optional[str] = None
    password_hash: Optional[str] = None
    otp: Optional[str] = None
    diet_goal: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True


class UserRead(UserCreate):
    id: int
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
