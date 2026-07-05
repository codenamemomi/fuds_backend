from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from api.v1.models.marketplace import MarketplaceFrequency


class MarketplaceCreate(BaseModel):
    user_id: int
    item_list: list[str] = Field(..., min_length=1)
    frequency: MarketplaceFrequency
    next_delivery: Optional[datetime] = None
    status: str = "active"


class MarketplaceRead(MarketplaceCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
